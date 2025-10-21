"""fix updated_at default not null in users"""

from alembic import op

revision = "f8853337fe7b"
down_revision = "dac7cb15e79b"
branch_labels = None
depends_on = None

def upgrade():
    # Asegurar que la columna tenga un valor por defecto y no quede nula
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN updated_at SET DEFAULT now();
    """)
    op.execute("""
        UPDATE users SET updated_at = now() WHERE updated_at IS NULL;
    """)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN updated_at SET NOT NULL;
    """)
    
def downgrade():
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN updated_at DROP NOT NULL;
    """)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN updated_at DROP DEFAULT;
    """)
