"""
Interactive CLI approval gate for mapping plans.

Prompts the user to approve, edit, or reject a mapping plan
before PVMAP generation begins. Not an ADK agent — plain Python
function called between agent graph sections.
"""

import enum
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class ApprovalResult(enum.Enum):
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


def request_approval(plan_path: str) -> ApprovalResult:
    """
    Prompt user to approve, edit, or reject the mapping plan.

    Args:
        plan_path: Path to the mapping plan markdown file

    Returns:
        ApprovalResult indicating user's decision
    """
    print(f"\n{'=' * 60}")
    print(f"Mapping plan saved to: {plan_path}")
    print(f"{'=' * 60}")

    plan_content = Path(plan_path).read_text()
    print(plan_content)
    print(f"\n{'=' * 60}")

    while True:
        choice = input("\n[A]pprove  |  [E]dit (opens in $EDITOR)  |  [R]eject (abort)\n> ").strip().lower()

        if choice == 'a':
            logger.info("Mapping plan approved by user")
            return ApprovalResult.APPROVED

        elif choice == 'e':
            editor = os.environ.get('EDITOR', 'vi')
            logger.info("Opening plan in %s for editing", editor)
            subprocess.run([editor, plan_path], check=False)
            logger.info("Plan edited by user, continuing with modified plan")
            return ApprovalResult.EDITED

        elif choice == 'r':
            logger.info("Mapping plan rejected by user")
            return ApprovalResult.REJECTED

        else:
            print(f"Invalid choice: '{choice}'. Please enter A, E, or R.")


def read_plan_file(plan_path: str) -> str:
    """
    Read a mapping plan file from disk.

    Args:
        plan_path: Path to the mapping plan file

    Returns:
        Plan content as string

    Raises:
        FileNotFoundError: If plan file does not exist
    """
    path = Path(plan_path)
    if not path.exists():
        raise FileNotFoundError(f"Mapping plan not found: {plan_path}")
    return path.read_text()
