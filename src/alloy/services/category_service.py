from datetime import datetime, UTC
from typing import List
from fastapi import HTTPException, status

from alloy.repositories.category_repository import CategoryRepository
from alloy.models.category_schemas import CategoryCreateUpdate
from alloy.models.auth_schemas import RoleEnum


class CategoryService:
    def __init__(self, category_repo: CategoryRepository):
        self.category_repo = category_repo

    def _ensure_admin(self, current_user: dict) -> None:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Category directory management is available only to the Administrator"
            )

    async def _format_admin_category(self, cat: dict) -> dict:
        cat_id = str(cat["_id"])
        cat_name = cat["name"]
        active_count, total_count = await self.category_repo.count_events_for_category(cat_id, cat_name)

        return {
            "id": cat_id,
            "name": cat_name,
            "active_events_count": active_count,
            "total_events_count": total_count,
            "is_archived": cat.get("is_archived", False),
            "created_at": cat["created_at"],
            "updated_at": cat.get("updated_at")
        }

    async def get_public_categories(self) -> List[dict]:
        categories = await self.category_repo.get_all_categories(include_archived=False)
        return [
            {"id": str(c["_id"]), "name": c["name"]}
            for c in categories
        ]

    async def get_all_categories_for_admin(self, current_user: dict) -> List[dict]:
        self._ensure_admin(current_user)
        categories = await self.category_repo.get_all_categories(include_archived=True)
        return [await self._format_admin_category(c) for c in categories]

    async def create_category(
        self, cat_in: CategoryCreateUpdate, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)

        existing = await self.category_repo.get_by_name_case_insensitive(cat_in.name)
        if existing:
            if existing.get("is_archived"):
                restored = await self.category_repo.update_category(
                    str(existing["_id"]),
                    {"is_archived": False, "name": cat_in.name}
                )
                return await self._format_admin_category(restored)

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this name already exists"
            )

        now = datetime.now(UTC)
        cat_doc = {
            "name": cat_in.name,
            "is_archived": False,
            "created_at": now,
            "updated_at": now
        }
        created = await self.category_repo.create_category(cat_doc)
        return await self._format_admin_category(created)

    async def update_category(
        self, category_id: str, cat_in: CategoryCreateUpdate, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)

        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        duplicate = await self.category_repo.get_by_name_case_insensitive(cat_in.name)
        if duplicate and str(duplicate["_id"]) != category_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another category with this name already exists"
            )

        updated = await self.category_repo.update_category(
            category_id,
            {"name": cat_in.name, "is_archived": False}
        )
        return await self._format_admin_category(updated)

    async def delete_or_archive_category(
        self, category_id: str, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)

        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        cat_name = category["name"]
        _, total_events = await self.category_repo.count_events_for_category(category_id, cat_name)

        if total_events > 0:
            await self.category_repo.update_category(category_id, {"is_archived": True})
            return {
                "id": category_id,
                "name": cat_name,
                "action": "archived",
                "message": f"Events are linked to the category ({total_events} items), so it has been moved to a hidden (archived) status"
            }

        await self.category_repo.delete_category_permanently(category_id)
        return {
            "id": category_id,
            "name": cat_name,
            "action": "deleted",
            "message": "Category has been permanently deleted from the directory"
        }
