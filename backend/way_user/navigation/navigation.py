from typing import Any, Dict, List


class NavigationConfig:
    @staticmethod
    def get_navigation(user: Any) -> List[Dict[str, Any]]:
        return [
            {"id": "dashboard", "label": "Dashboard", "path": "/dashboard"},
            {"id": "profile", "label": "Profile", "path": "/profile"},
            {"id": "wallet", "label": "Wallet", "path": "/wallet"},
            {"id": "skills", "label": "Skills", "path": "/skills"},
        ]

    @staticmethod
    def get_user_role(user: Any) -> str:
        if getattr(user, "is_superuser", False):
            return "admin"
        if getattr(user, "is_staff", False):
            return "staff"
        return "user"
