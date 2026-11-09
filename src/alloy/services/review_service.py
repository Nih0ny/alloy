from datetime import datetime, UTC
from typing import List
from fastapi import HTTPException, status

from alloy.repositories.review_repository import ReviewRepository
from alloy.repositories.event_repository import EventRepository
from alloy.repositories.application_repository import ApplicationRepository
from alloy.repositories.user_repository import UserRepository
from alloy.models.review_schemas import (
    OrganizerReviewVolunteerCreate,
    VolunteerReviewOrganizerCreate,
)
from alloy.models.event_schemas import EventLifecycleStatusEnum
from alloy.models.application_schemas import ApplicationStatusEnum
from alloy.models.auth_schemas import RoleEnum
from alloy.services.notification_service import NotificationService
from alloy.models.notification_schemas import NotificationTypeEnum

ALLOWED_REVIEW_EVENT_STATUSES = [
    EventLifecycleStatusEnum.in_process.value,
    EventLifecycleStatusEnum.completed.value,
]

class ReviewService:
    def __init__(
        self,
        review_repository: ReviewRepository,
        event_repository: EventRepository,
        app_repository: ApplicationRepository,
        user_repository: UserRepository,
        notif_service: NotificationService
    ):
        self.review_repository = review_repository
        self.event_repository = event_repository
        self.app_repository = app_repository
        self.user_repository = user_repository
        self.notif_service = notif_service

    def _extract_user_name(self, user: dict | None) -> str:
        if not user:
            return "Unknown User"
        return user.get("profile", {}).get("full_name") or user["email"]

    async def _save_and_recalculate(
        self,
        event: dict,
        reviewer: dict,
        reviewee: dict,
        rating: int,
        comment: str
    ) -> dict:
        event_id = str(event["_id"])
        reviewer_id = str(reviewer["_id"])
        reviewee_id = str(reviewee["_id"])

        existing = await self.review_repository.get_existing_review(event_id, reviewer_id, reviewee_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already left a review for this user within this event"
            )

        now = datetime.now(UTC)
        review_doc = {
            "event_id": event_id,
            "reviewer_id": reviewer_id,
            "reviewee_id": reviewee_id,
            "rating": rating,
            "comment": comment.strip(),
            "created_at": now
        }

        created = await self.review_repository.create_review(review_doc)

        new_avg_rating = await self.review_repository.calculate_average_rating(reviewee_id)
        await self.user_repository.update_user_rating(reviewee_id, new_avg_rating)

        reviewer_name = self._extract_user_name(reviewer)

        await self.notif_service.notify_user(
            user_id=reviewee_id,
            notif_type=NotificationTypeEnum.new_review,
            title="You received a new review!",
            message=(
                f"User {reviewer_name} has rated cooperation with you in the event «{event['title']}» "
                f"at {rating} out of 5 stars. Your updated rating is {new_avg_rating}."
            ),
            related_entity_id=event_id
        )

        return {
            "id": str(created["_id"]),
            "event_id": event_id,
            "event_title": event["title"],
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "reviewee_id": reviewee_id,
            "reviewee_name": self._extract_user_name(reviewee),
            "rating": created["rating"],
            "comment": created.get("comment"),
            "reviewee_new_average_rating": new_avg_rating,
            "created_at": created["created_at"]
        }

    async def review_volunteer_by_organizer(
        self,
        event_id: str,
        review_in: OrganizerReviewVolunteerCreate,
        current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["organizer_id"] != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the organizer of this event can review involved volunteers"
            )

        if event["status"] not in ALLOWED_REVIEW_EVENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviewing is available only for events in 'In Process' or 'Completed' status"
            )

        application = await self.app_repository.get_by_event_and_volunteer(
            event_id, review_in.volunteer_id
        )
        if not application or application["status"] != ApplicationStatusEnum.approved.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can only review a volunteer whose application for this event has 'Approved' status"
            )

        volunteer = await self.user_repository.get_user_by_id(review_in.volunteer_id)
        if not volunteer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")

        return await self._save_and_recalculate(
            event=event,
            reviewer=current_user,
            reviewee=volunteer,
            rating=review_in.rating,
            comment=review_in.comment
        )

    async def review_organizer_by_volunteer(
        self,
        event_id: str,
        review_in: VolunteerReviewOrganizerCreate,
        current_user: dict
    ) -> dict:
        if current_user.get("role") != RoleEnum.volunteer.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a volunteer can leave this type of review"
            )

        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["status"] not in ALLOWED_REVIEW_EVENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviewing is unavailable for this event ('In Process' or 'Completed' status required)"
            )

        volunteer_id = str(current_user["_id"])

        application = await self.app_repository.get_by_event_and_volunteer(event_id, volunteer_id)
        if not application or application["status"] != ApplicationStatusEnum.approved.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can review the organizer only if your application for this event was 'Approved'"
            )

        organizer = await self.user_repository.get_user_by_id(event["organizer_id"])
        if not organizer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizer not found")

        return await self._save_and_recalculate(
            event=event,
            reviewer=current_user,
            reviewee=organizer,
            rating=review_in.rating,
            comment=review_in.comment
        )

    async def get_review_form_context(
        self, event_id: str, target_user_id: str, current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        target_user = await self.user_repository.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        reviewer_id = str(current_user["_id"])
        existing = await self.review_repository.get_existing_review(event_id, reviewer_id, target_user_id)
        status_ok = event["status"] in ALLOWED_REVIEW_EVENT_STATUSES

        return {
            "event_id": event_id,
            "event_title": event["title"],
            "reviewee_id": target_user_id,
            "reviewee_name": self._extract_user_name(target_user),
            "reviewee_role": target_user["role"],
            "already_reviewed": existing is not None,
            "can_review": status_ok and (existing is None)
        }

    async def get_event_reviews(self, event_id: str) -> List[dict]:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        raw_reviews = await self.review_repository.get_reviews_by_event(event_id)
        formatted = []
        for rev in raw_reviews:
            reviewer = await self.user_repository.get_user_by_id(rev["reviewer_id"])
            reviewee = await self.user_repository.get_user_by_id(rev["reviewee_id"])
            reviewee_rating = reviewee.get("profile", {}).get("rating", 0.0) if reviewee else 0.0

            formatted.append({
                "id": str(rev["_id"]),
                "event_id": rev["event_id"],
                "event_title": event["title"],
                "reviewer_id": rev["reviewer_id"],
                "reviewer_name": self._extract_user_name(reviewer),
                "reviewee_id": rev["reviewee_id"],
                "reviewee_name": self._extract_user_name(reviewee),
                "rating": rev["rating"],
                "comment": rev.get("comment"),
                "reviewee_new_average_rating": reviewee_rating,
                "created_at": rev["created_at"]
            })
        return formatted
