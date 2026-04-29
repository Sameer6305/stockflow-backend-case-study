# Database Layer

This folder contains explicit helpers for database initialization and teardown.
The app factory keeps configuration separate from session control so the codebase
can later support migrations, seeding, and environment-specific bootstrap steps.
