from ynoy.cli.handlers.benchmark import handle_benchmark
from ynoy.cli.handlers.bootstrap import handle_bootstrap
from ynoy.cli.handlers.corpus import handle_corpus
from ynoy.cli.handlers.database import handle_database
from ynoy.cli.handlers.doctor import handle_doctor
from ynoy.cli.handlers.erase import handle_erase
from ynoy.cli.handlers.inference import handle_advisor, handle_mirror
from ynoy.cli.handlers.manager import handle_manager
from ynoy.cli.handlers.memory import handle_memory
from ynoy.cli.handlers.persona import handle_persona
from ynoy.cli.handlers.review import handle_review
from ynoy.cli.handlers.study import handle_study

__all__ = [
    "handle_advisor",
    "handle_benchmark",
    "handle_bootstrap",
    "handle_corpus",
    "handle_database",
    "handle_doctor",
    "handle_erase",
    "handle_manager",
    "handle_memory",
    "handle_mirror",
    "handle_persona",
    "handle_review",
    "handle_study",
]
