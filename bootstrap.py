"""Bootstraps users and other DB entities for testing/dev."""

import time
import logging

from arxiv.submission.services import classic
from arxiv.submission.services.classic import bootstrap
from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes
from submit.factory import create_ui_web_app

logging.getLogger("arxiv.submission.services.classic.interpolate").setLevel(
    logging.ERROR
)
logging.getLogger("arxiv.base.alerts").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

app = create_ui_web_app()

with app.app_context():
    session = classic.current_session()
    engine = classic.util.current_engine()
    logger.info("Waiting for database server to be available")
    logger.info(app.config["SQLALCHEMY_DATABASE_URI"])

    wait = 2
    while True:
        try:
            session.execute("SELECT 1")
            break
        except Exception as e:
            logger.info(e)
            logger.info(f"...waiting {wait} seconds...")
            time.sleep(wait)
            wait *= 2

    logger.info("Checking for database")
    if not engine.dialect.has_table(engine, "arXiv_submissions"):
        created_users = []
        logger.info("Database not yet initialized; creating tables")
        classic.create_all()

        logger.info("Populate with base data...")
        licenses = classic.bootstrap.licenses()
        for obj in licenses:
            session.add(obj)
        logger.info("Added %i licenses", len(licenses))
        policy_classes = classic.bootstrap.policy_classes()
        for obj in policy_classes:
            session.add(obj)
        logger.info("Added %i policy classes", len(policy_classes))
        categories = classic.bootstrap.categories()
        for obj in categories:
            session.add(obj)
        logger.info("Added %i categories", len(categories))
        users = classic.bootstrap.users(10)
        for obj in users:
            session.add(obj)
            created_users.append(obj)
        logger.info("Added %i users", len(users))
        session.commit()

        scope = [
            scopes.READ_PUBLIC,
            scopes.CREATE_SUBMISSION,
            scopes.EDIT_SUBMISSION,
            scopes.VIEW_SUBMISSION,
            scopes.DELETE_SUBMISSION,
            scopes.READ_UPLOAD,
            scopes.WRITE_UPLOAD,
            scopes.DELETE_UPLOAD_FILE,
            scopes.READ_UPLOAD_LOGS,
            scopes.READ_COMPILE,
            scopes.CREATE_COMPILE,
            scopes.READ_PREVIEW,
            scopes.CREATE_PREVIEW,
        ]
        for user in created_users:
            token = generate_token(
                user.user_id,
                user.email,
                user.email,
                scope=scope,
                first_name=user.first_name,
                last_name=user.last_name,
                suffix_name=user.suffix_name,
                endorsements=["*.*"],
            )
            print(user.user_id, user.email, token)

        exit(0)
    logger.info("Nothing to do")
