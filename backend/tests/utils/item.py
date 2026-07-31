from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models import Item, ItemCreate, OrganizationMember
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


async def create_random_item(db: AsyncSession) -> Item:
    user = await create_random_user(db)
    owner_id = user.id
    assert owner_id is not None
    # Items are tenant-scoped; attach to the owner's personal organization
    membership = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.user_id == owner_id,
                OrganizationMember.role == "owner",
            )
        )
    ).first()
    organization_id = membership.organization_id if membership else None
    title = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(title=title, description=description)
    return await crud.create_item(
        session=db,
        item_in=item_in,
        owner_id=owner_id,
        organization_id=organization_id,
    )
