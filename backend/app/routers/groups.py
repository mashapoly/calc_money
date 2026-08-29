from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, get_group_member
from ..ws_manager import manager

router = APIRouter(prefix="/api/groups", tags=["groups"])

# Fixed reference rates (units of currency per 1 RUB's worth is implied by
# "how many RUB is 1 unit of this currency worth"). These are static
# approximations for demo purposes, not a live feed.
EXCHANGE_RATES_TO_RUB = {
    "RUB": 1.0,
    "USD": 90.0,
    "EUR": 98.0,
    "GBP": 115.0,
    "KZT": 0.19,
}


def _convert_group_currency(db: Session, group: models.Group, new_currency: str) -> None:
    """Rescales every expense/share amount in the group so existing totals keep
    the same real-world value when the group's currency changes."""
    old_currency = group.currency
    if new_currency == old_currency:
        return

    rate = EXCHANGE_RATES_TO_RUB[old_currency] / EXCHANGE_RATES_TO_RUB[new_currency]

    expenses = db.query(models.Expense).filter(models.Expense.group_id == group.id).all()
    for expense in expenses:
        expense.amount = round(expense.amount * rate, 2)

    shares = (
        db.query(models.ExpenseShare)
        .join(models.Expense, models.ExpenseShare.expense_id == models.Expense.id)
        .filter(models.Expense.group_id == group.id)
        .all()
    )
    for share in shares:
        share.share_amount = round(share.share_amount * rate, 2)


def _group_detail(group: models.Group) -> schemas.GroupDetailOut:
    return schemas.GroupDetailOut(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        currency=group.currency,
        owner_id=group.owner_id,
        created_at=group.created_at,
        members=[
            schemas.GroupMemberOut(user_id=m.user_id, username=m.user.username)
            for m in group.members
        ],
    )


@router.post("", response_model=schemas.GroupDetailOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: schemas.GroupCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = models.Group(name=payload.name, currency=payload.currency, owner_id=current_user.id)
    db.add(group)
    db.flush()

    member = models.GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(member)
    db.commit()
    db.refresh(group)

    return _group_detail(group)


@router.get("", response_model=list[schemas.GroupOut])
def list_my_groups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    groups = (
        db.query(models.Group)
        .join(models.GroupMember, models.GroupMember.group_id == models.Group.id)
        .filter(models.GroupMember.user_id == current_user.id)
        .all()
    )
    return groups


@router.post("/join", response_model=schemas.GroupDetailOut)
async def join_group(
    payload: schemas.GroupJoin,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = (
        db.query(models.Group)
        .options(joinedload(models.Group.members).joinedload(models.GroupMember.user))
        .filter(models.Group.invite_code == payload.invite_code)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа с такой ссылкой не найдена")

    existing = (
        db.query(models.GroupMember)
        .filter(models.GroupMember.group_id == group.id, models.GroupMember.user_id == current_user.id)
        .first()
    )
    if not existing:
        member = models.GroupMember(group_id=group.id, user_id=current_user.id)
        db.add(member)
        db.commit()
        db.refresh(group)

        await manager.broadcast(
            group.id,
            "member_joined",
            {"user_id": current_user.id, "username": current_user.username},
        )

    return _group_detail(group)


@router.get("/{group_id}", response_model=schemas.GroupDetailOut)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_member(group_id, db, current_user)
    group = (
        db.query(models.Group)
        .options(joinedload(models.Group.members).joinedload(models.GroupMember.user))
        .filter(models.Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return _group_detail(group)


def _get_owned_group(group_id: int, db: Session, current_user: models.User) -> models.Group:
    get_group_member(group_id, db, current_user)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Изменять группу может только её создатель")
    return group


@router.patch("/{group_id}", response_model=schemas.GroupDetailOut)
async def update_group(
    group_id: int,
    payload: schemas.GroupUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Any member (not just the owner) may rename the group or change its currency.
    get_group_member(group_id, db, current_user)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    if payload.name is not None:
        group.name = payload.name

    if payload.currency is not None and payload.currency != group.currency:
        _convert_group_currency(db, group, payload.currency)
        group.currency = payload.currency

    db.commit()
    db.refresh(group)

    group = (
        db.query(models.Group)
        .options(joinedload(models.Group.members).joinedload(models.GroupMember.user))
        .filter(models.Group.id == group_id)
        .first()
    )

    result = _group_detail(group)
    await manager.broadcast(group_id, "group_updated", result.model_dump(mode="json"))
    return result


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = _get_owned_group(group_id, db, current_user)

    db.delete(group)
    db.commit()

    await manager.broadcast(group_id, "group_deleted", {"group_id": group_id})


@router.post("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    member = get_group_member(group_id, db, current_user)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()

    if group and group.owner_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Создатель не может выйти из группы — удалите группу вместо этого",
        )

    db.delete(member)
    db.commit()

    await manager.broadcast(
        group_id,
        "member_left",
        {"user_id": current_user.id, "username": current_user.username},
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = _get_owned_group(group_id, db, current_user)

    if user_id == group.owner_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить создателя группы")

    member = (
        db.query(models.GroupMember)
        .filter(models.GroupMember.group_id == group_id, models.GroupMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Этот пользователь не состоит в группе")

    removed_user = db.query(models.User).filter(models.User.id == user_id).first()
    db.delete(member)
    db.commit()

    await manager.broadcast(
        group_id,
        "member_removed",
        {"user_id": user_id, "username": removed_user.username if removed_user else ""},
    )
