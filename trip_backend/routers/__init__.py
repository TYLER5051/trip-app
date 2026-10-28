"""API routers for the Smart Trip backend.

Each module exposes a single ``APIRouter`` instance named ``router``:

- ``authentication`` — /register, /login
- ``trips``          — /trips/... + nested categories
- ``items``          — /items/...
- ``participants``   — /trips/{id}/leave, /participants/{user_id}
- приєднання до поїздки — лише за інвайт-токеном: POST /trips/invite/{token} (у ``participants``)

Спільна залежність ``get_current_user`` знаходиться у ``deps.py``
"""
