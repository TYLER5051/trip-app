from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, ROUND_HALF_UP

from database import get_db
from deps import get_current_user, get_accessible_trip, ensure_active_trip
from activity_log import log_activity
from rate_limit import limiter

import models, schemas

router = APIRouter(prefix="/trips/{trip_id}/budget")


def _bank_for_trip(db: Session, trip_id: int) -> Decimal:
    """Поточний залишок спільного банку: внески мінус оплати з банку."""
    contributions = (
        db.query(func.coalesce(func.sum(models.Contribution.amount), Decimal("0")))
        .filter(models.Contribution.trip_id == trip_id)
        .scalar()
    )
    pool_expenses = (
        db.query(func.coalesce(func.sum(models.Expense.amount), Decimal("0")))
        .filter(models.Expense.trip_id == trip_id, models.Expense.paid_from_pool.is_(True))
        .scalar()
    )
    return contributions - pool_expenses


def _check_bank_after(
    db: Session,
    trip_id: int,
    excluding_expense_id: int | None = None,
    excluding_contribution_id: int | None = None,
    new_contribution_amount: Decimal = Decimal("0"),
    new_pool_expense_amount: Decimal = Decimal("0"),
) -> None:
    """Банк не повинен піти в мінус після майбутньої зміни."""
    bank = _bank_for_trip(db, trip_id)

    if excluding_expense_id is not None:
        old = db.get(models.Expense, excluding_expense_id)
        if old is not None and old.paid_from_pool:
            bank += old.amount

    if excluding_contribution_id is not None:
        old = db.get(models.Contribution, excluding_contribution_id)
        if old is not None:
            bank -= old.amount

    bank = bank + new_contribution_amount - new_pool_expense_amount

    if bank < Decimal("0"):
        raise HTTPException(
            status_code=400,
            detail="Недостатньо коштів у банку. Поповніть банк або позначте оплату як особисту",
        )


def _member_ids(trip: models.Trip) -> set[int]:
    """ID учасників поїздки разом з організатором."""
    ids = {u.id for u in trip.participants}
    if trip.owner_id is not None:
        ids.add(trip.owner_id)
    return ids


def _split_check(
    trip: models.Trip,
    amount: Decimal,
    paid_by_user_id: int | None,
    shares: list[schemas.ExpenseShareRequest],
) -> None:
    """Перевірки розбиття витрати: учасники і платник ∈ поїздки, без дублікатів, сума сходиться."""
    members = _member_ids(trip)
    if not all(s.user_id in members for s in shares):
        raise HTTPException(status_code=400, detail="Усі учасники часток мають бути учасниками поїздки")
    if paid_by_user_id is not None and paid_by_user_id not in members:
        raise HTTPException(status_code=400, detail="Платник має бути учасником поїздки")
    if len({s.user_id for s in shares}) != len(shares):
        raise HTTPException(status_code=400, detail="Користувачі у частках мають бути унікальними")
    shares_sum = sum((s.amount for s in shares), Decimal("0"))
    if shares_sum != amount:
        raise HTTPException(status_code=400, detail="Сума часток має дорівнювати загальній сумі витрати")


def _compute_balances(db: Session, trip: models.Trip) -> schemas.BudgetOverviewResponse:
    contributions = db.query(models.Contribution).filter(models.Contribution.trip_id == trip.id).all()
    expenses = (
        db.query(models.Expense)
        .options(selectinload(models.Expense.shares))
        .filter(models.Expense.trip_id == trip.id)
        .all()
    )

    balances = {
        u.id: {"user": u, "contributed": Decimal("0"), "paid_by_self": Decimal("0"), "share_costs": Decimal("0")}
        for u in trip.participants
    }
    if trip.owner_id is not None:
        balances[trip.owner_id] = {
            "user": trip.owner, "contributed": Decimal("0"), "paid_by_self": Decimal("0"), "share_costs": Decimal("0")
        }

    deleted_contributed = deleted_paid_by_self = deleted_share_costs = Decimal("0")
    total_contributions = total_pool_expense = total_expenses = Decimal("0")

    for c in contributions:
        total_contributions += c.amount
        if c.user_id is not None and c.user_id in balances:
            balances[c.user_id]["contributed"] += c.amount
        else:
            deleted_contributed += c.amount

    for e in expenses:
        total_expenses += e.amount
        if e.paid_from_pool:
            total_pool_expense += e.amount
        elif e.paid_by_user_id is not None and e.paid_by_user_id in balances:
            balances[e.paid_by_user_id]["paid_by_self"] += e.amount
        else:
            deleted_paid_by_self += e.amount

        for share in e.shares:
            if share.user_id is not None and share.user_id in balances:
                balances[share.user_id]["share_costs"] += share.amount
            else:
                deleted_share_costs += share.amount

    participants = [
        schemas.ParticipantBalance(
            user=d["user"],
            contributed=d["contributed"],
            paid_by_self=d["paid_by_self"],
            share_costs=d["share_costs"],
            net=d["contributed"] + d["paid_by_self"] - d["share_costs"],
        )
        for d in balances.values()
    ]

    return schemas.BudgetOverviewResponse(
        bank_balance=total_contributions - total_pool_expense,
        total_contributions=total_contributions,
        total_expenses=total_expenses,
        participants=participants,
        deleted_users=schemas.DeleteUsersSummary(
            contributed=deleted_contributed,
            share_costs=deleted_share_costs,
            net=deleted_contributed + deleted_paid_by_self - deleted_share_costs,
        ),
    )


def _compute_settlement(balances, bank_balance: Decimal) -> schemas.SettlementResponse:
    """Скільки і кому виплатити з банку та хто кому переказує.
    Видалених користувачів (user=None) виключаємо — вони покриті через bank_balance/nоту."""
    working = {
        p.user.id: {"user": p.user, "net": p.net}
        for p in balances
        if p.user is not None
    }

    creditors = [item for item in working.values() if item["net"] > Decimal("0")]
    sum_pos = sum((item["net"] for item in creditors), Decimal("0"))

    bank_payouts: list[schemas.BankPayout] = []

    if bank_balance > Decimal("0") and sum_pos > Decimal("0"):
        ratio = Decimal("1") if bank_balance >= sum_pos else bank_balance / sum_pos
        raw_payouts = [
            {"item": item, "payout": (item["net"] * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}
            for item in creditors
        ]

        total_payouts = sum((p["payout"] for p in raw_payouts), Decimal("0"))
        diff = min(bank_balance, sum_pos) - total_payouts
        if diff != Decimal("0"):
            max(raw_payouts, key=lambda p: p["item"]["net"])["payout"] += diff

        for p in raw_payouts:
            if p["payout"] > Decimal("0"):
                p["item"]["net"] -= p["payout"]
                bank_payouts.append(schemas.BankPayout(user=p["item"]["user"], amount=p["payout"]))

    debtors = [
        {"user": item["user"], "amount": abs(item["net"])}
        for item in working.values()
        if item["net"] < Decimal("0")
    ]
    rem_creditors = [
        {"user": item["user"], "amount": item["net"]}
        for item in working.values()
        if item["net"] > Decimal("0")
    ]

    transfers: list[schemas.SettlementTransfer] = []

    while debtors and rem_creditors:
        debtors.sort(key=lambda x: x["amount"], reverse=True)
        rem_creditors.sort(key=lambda x: x["amount"], reverse=True)

        debtor = debtors[0]
        creditor = rem_creditors[0]
        amount = min(debtor["amount"], creditor["amount"])

        transfers.append(
            schemas.SettlementTransfer(from_user=debtor["user"], to_user=creditor["user"], amount=amount)
        )
        debtor["amount"] -= amount
        creditor["amount"] -= amount
        if debtor["amount"] == Decimal("0"):
            debtors.pop(0)
        if creditor["amount"] == Decimal("0"):
            rem_creditors.pop(0)

    note_parts: list[str] = []
    if bank_balance > sum_pos:
        note_parts.append(
            f"У банку залишилося {bank_balance - sum_pos} нерозподілених коштів (внески видалених учасників)."
        )
    if debtors or rem_creditors:
        note_parts.append(
            "Частина взаєморозрахунків не перекрита через частки або оплати видалених учасників."
        )

    return schemas.SettlementResponse(
        bank_balance=bank_balance,
        transfers=transfers,
        bank_payouts=bank_payouts,
        deleted_users_note=" ".join(note_parts) if note_parts else None,
    )


def _lock_trip(db: Session, trip: models.Trip) -> None:
    """Блокує рядок trip FOR UPDATE, щоб виключити перегони за залишком банку."""
    db.query(models.Trip).filter(models.Trip.id == trip.id).with_for_update().first()


def _can_manage(current_user: models.User, trip: models.Trip, obj) -> bool:
    """Редагувати/видаляти запис може його автор або організатор поїздки."""
    return trip.owner_id == current_user.id or obj.created_by_id == current_user.id


def _get_contribution(db: Session, trip_id: int, contribution_id: int, for_update: bool = False):
    query = db.query(models.Contribution).filter(
        models.Contribution.id == contribution_id,
        models.Contribution.trip_id == trip_id,
    )
    if for_update:
        query = query.with_for_update()
    contribution = query.first()
    if contribution is None:
        raise HTTPException(status_code=404, detail="Внесок не знайдено")
    return contribution


_EXPENSE_LOAD = (
    selectinload(models.Expense.shares).selectinload(models.ExpenseShare.user),
    selectinload(models.Expense.paid_by_user),
    selectinload(models.Expense.created_by),
)


def _get_expense(db: Session, trip_id: int, expense_id: int, for_update: bool = False):
    query = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.trip_id == trip_id,
    )
    if for_update:
        query = query.with_for_update()
    expense = query.first()
    if expense is None:
        raise HTTPException(status_code=404, detail="Витрату не знайдено")
    return expense


def _reload_expense(db: Session, expense_id: int):
    return (
        db.query(models.Expense)
        .options(*_EXPENSE_LOAD)
        .filter(models.Expense.id == expense_id)
        .populate_existing()
        .first()
    )


@router.get("", response_model=schemas.BudgetListResponse)
@limiter.limit("60/minute")
def list_budget(
    request: Request,
    trip_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
):
    contributions_q = db.query(models.Contribution).filter(models.Contribution.trip_id == trip.id)
    expenses_q = db.query(models.Expense).filter(models.Expense.trip_id == trip.id)

    total = contributions_q.count() + expenses_q.count()
    contributions = (
        contributions_q
        .order_by(models.Contribution.created_at.desc(), models.Contribution.id.desc())
        .offset(offset).limit(limit).all()
    )
    expenses = (
        expenses_q
        .options(*_EXPENSE_LOAD)
        .order_by(models.Expense.created_at.desc(), models.Expense.id.desc())
        .offset(offset).limit(limit).all()
    )
    return schemas.BudgetListResponse(
        contributions=contributions,
        expenses=expenses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/overview", response_model=schemas.BudgetOverviewResponse)
@limiter.limit("60/minute")
def get_budget_overview(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
):
    return _compute_balances(db, trip)


@router.get("/settlement", response_model=schemas.SettlementResponse)
@limiter.limit("60/minute")
def get_settlement(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
):
    overview = _compute_balances(db, trip)
    return _compute_settlement(overview.participants, overview.bank_balance)


@router.post("/contributions", response_model=schemas.ContributionResponse)
@limiter.limit("60/minute")
def create_contribution(
    request: Request,
    payload: schemas.ContributionCreate,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    contribution = models.Contribution(
        trip_id=trip.id,
        user_id=current_user.id,
        amount=payload.amount,
        note=payload.note,
        created_by_id=current_user.id,
    )
    db.add(contribution)
    db.flush()
    log_activity(db, trip.id, current_user.id, "contribution_added",
                 {"contribution_id": contribution.id, "amount": str(contribution.amount)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")
    
    db.refresh(contribution)
    return contribution


@router.patch("/contributions/{contribution_id}", response_model=schemas.ContributionResponse)
@limiter.limit("60/minute")
def update_contribution(
    request: Request,
    contribution_id: int,
    payload: schemas.ContributionUpdate,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    contribution = _get_contribution(db, trip.id, contribution_id, for_update=True)
    if not _can_manage(current_user, trip, contribution):
        raise HTTPException(status_code=403, detail="Ви можете змінювати лише власні внески (або організатор)")

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Немає даних для оновлення")

    amount = fields.get("amount", contribution.amount)
    _check_bank_after(db, trip.id, excluding_contribution_id=contribution.id,
                      new_contribution_amount=amount)

    contribution.amount = amount
    if "note" in fields:
        contribution.note = fields["note"]

    log_activity(db, trip.id, current_user.id, "contribution_updated",
                 {"contribution_id": contribution.id, "amount": str(contribution.amount)})

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")

    db.refresh(contribution)
    return contribution


@router.delete("/contributions/{contribution_id}")
@limiter.limit("60/minute")
def delete_contribution(
    request: Request,
    contribution_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    contribution = _get_contribution(db, trip.id, contribution_id, for_update=True)
    if not _can_manage(current_user, trip, contribution):
        raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні внески (або організатор)")

    _check_bank_after(db, trip.id, excluding_contribution_id=contribution.id)

    log_activity(db, trip.id, current_user.id, "contribution_deleted",
                 {"contribution_id": contribution.id, "amount": str(contribution.amount)})
    try:
        db.delete(contribution)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")
    return {"message": "Внесок видалено"}


@router.post("/expenses", response_model=schemas.ExpenseResponse)
@limiter.limit("60/minute")
def create_expense(
    request: Request,
    payload: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    _split_check(trip, payload.amount, payload.paid_by_user_id, payload.shares)
    _check_bank_after(db, trip.id, new_pool_expense_amount=payload.amount if payload.paid_from_pool else Decimal("0"))

    expense = models.Expense(
        trip_id=trip.id,
        name=payload.name,
        amount=payload.amount,
        paid_from_pool=payload.paid_from_pool,
        paid_by_user_id=payload.paid_by_user_id,
        note=payload.note,
        created_by_id=current_user.id,
    )
    db.add(expense)
    db.flush()
    for share in payload.shares:
        db.add(models.ExpenseShare(expense_id=expense.id, user_id=share.user_id, amount=share.amount))

    log_activity(db, trip.id, current_user.id, "expense_added",
                 {"expense_id": expense.id, "name": expense.name, "amount": str(expense.amount)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")
    return _reload_expense(db, expense.id)


@router.patch("/expenses/{expense_id}", response_model=schemas.ExpenseResponse)
@limiter.limit("60/minute")
def update_expense(
    request: Request,
    expense_id: int,
    payload: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    expense = _get_expense(db, trip.id, expense_id, for_update=True)
    if not _can_manage(current_user, trip, expense):
        raise HTTPException(status_code=403, detail="Ви можете змінювати лише власні витрати (або організатор)")

    if any(s.user_id is None for s in expense.shares) or (not expense.paid_from_pool and expense.paid_by_user_id is None):
        raise HTTPException(status_code=400, detail="Не можна редагувати витрату за участю видалених користувачів")

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Немає даних для оновлення")

    amount = fields["amount"] if "amount" in fields else expense.amount
    paid_from_pool = fields["paid_from_pool"] if fields.get("paid_from_pool") is not None else expense.paid_from_pool
    paid_by_user_id = fields["paid_by_user_id"] if "paid_by_user_id" in fields else expense.paid_by_user_id

    if not paid_from_pool and paid_by_user_id is None:
        raise HTTPException(status_code=400, detail="Для особистої оплати потрібно вказати платника")

    if "shares" in fields:
        _split_check(trip, amount, paid_by_user_id, payload.shares)
    elif "amount" in fields:
        existing_sum = sum((s.amount for s in expense.shares), Decimal("0"))
        if existing_sum != amount:
            raise HTTPException(status_code=400, detail="Разом зі зміною суми передайте нові частки")

    _check_bank_after(db, trip.id, excluding_expense_id=expense.id,
                      new_pool_expense_amount=amount if paid_from_pool else Decimal("0"))

    if "name" in fields:
        expense.name = fields["name"]
    expense.amount = amount
    expense.paid_from_pool = paid_from_pool
    expense.paid_by_user_id = paid_by_user_id
    if "note" in fields:
        expense.note = fields["note"]

    if "shares" in fields:
        for share in list(expense.shares):
            db.delete(share)
        db.flush()
        for share in payload.shares:
            expense.shares.append(models.ExpenseShare(user_id=share.user_id, amount=share.amount))

    log_activity(db, trip.id, current_user.id, "expense_updated",
                 {"expense_id": expense.id, "name": expense.name, "amount": str(expense.amount)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")
    return _reload_expense(db, expense.id)


@router.delete("/expenses/{expense_id}")
@limiter.limit("60/minute")
def delete_expense(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    current_user: models.User = Depends(get_current_user),
):
    ensure_active_trip(trip)
    _lock_trip(db, trip)

    expense = _get_expense(db, trip.id, expense_id, for_update=True)
    if not _can_manage(current_user, trip, expense):
        raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні витрати (або організатор)")

    log_activity(db, trip.id, current_user.id, "expense_deleted",
                 {"expense_id": expense.id, "name": expense.name, "amount": str(expense.amount)})
    try:
        db.delete(expense)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")
    return {"message": f"Витрату '{expense.name}' видалено"}
