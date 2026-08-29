import heapq

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, get_group_member
from ..ws_manager import manager

router = APIRouter(prefix="/api/groups/{group_id}/expenses", tags=["expenses"])

ROUND = 2
EPS = 0.01


def _expense_out(expense: models.Expense) -> schemas.ExpenseOut:
    return schemas.ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        description=expense.description,
        amount=expense.amount,
        paid_by_id=expense.paid_by_id,
        paid_by_username=expense.paid_by.username,
        created_by_id=expense.created_by_id,
        created_at=expense.created_at,
        shares=[
            schemas.ExpenseShareOut(
                user_id=s.user_id, username=s.user.username, share_amount=s.share_amount
            )
            for s in expense.shares
        ],
    )


def _member_ids(db: Session, group_id: int) -> set[int]:
    rows = db.query(models.GroupMember.user_id).filter(models.GroupMember.group_id == group_id).all()
    return {r[0] for r in rows}


def _compute_balances(db: Session, group_id: int) -> dict[int, float]:
    balances: dict[int, float] = {uid: 0.0 for uid in _member_ids(db, group_id)}

    expenses = (
        db.query(models.Expense)
        .options(joinedload(models.Expense.shares))
        .filter(models.Expense.group_id == group_id)
        .all()
    )
    for expense in expenses:
        balances[expense.paid_by_id] = balances.get(expense.paid_by_id, 0.0) + expense.amount
        for share in expense.shares:
            balances[share.user_id] = balances.get(share.user_id, 0.0) - share.share_amount

    return {uid: round(bal, ROUND) for uid, bal in balances.items()}


def _simplify_debts(balances: dict[int, float]) -> list[tuple[int, int, float]]:
    # Store as negative amounts so heapq (a min-heap) pops the largest credit/debt first.
    creditors = [(-bal, uid) for uid, bal in balances.items() if bal > EPS]
    debtors = [(bal, uid) for uid, bal in balances.items() if bal < -EPS]
    heapq.heapify(creditors)
    heapq.heapify(debtors)

    debts: list[tuple[int, int, float]] = []
    while creditors and debtors:
        credit_amt, creditor_id = heapq.heappop(creditors)  # credit_amt is negative
        debt_amt, debtor_id = heapq.heappop(debtors)  # debt_amt is negative

        pay = min(-credit_amt, -debt_amt)
        pay = round(pay, ROUND)
        if pay > EPS:
            debts.append((debtor_id, creditor_id, pay))

        remaining_credit = -credit_amt - pay
        remaining_debt = -debt_amt - pay

        if remaining_credit > EPS:
            heapq.heappush(creditors, (-remaining_credit, creditor_id))
        if remaining_debt > EPS:
            heapq.heappush(debtors, (-remaining_debt, debtor_id))

    return debts


def _balances_payload(db: Session, group_id: int) -> schemas.GroupBalancesOut:
    balances = _compute_balances(db, group_id)
    users = {u.id: u.username for u in db.query(models.User).filter(models.User.id.in_(balances.keys())).all()}

    balance_out = [
        schemas.BalanceOut(user_id=uid, username=users.get(uid, "?"), balance=bal)
        for uid, bal in balances.items()
    ]
    debts = _simplify_debts(balances)
    debt_out = [
        schemas.DebtOut(
            from_user_id=frm,
            from_username=users.get(frm, "?"),
            to_user_id=to,
            to_username=users.get(to, "?"),
            amount=amt,
        )
        for frm, to, amt in debts
    ]
    return schemas.GroupBalancesOut(balances=balance_out, debts=debt_out)


@router.post("", response_model=schemas.ExpenseOut, status_code=201)
async def add_expense(
    group_id: int,
    payload: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_member(group_id, db, current_user)
    member_ids = _member_ids(db, group_id)

    if payload.paid_by_id not in member_ids:
        raise HTTPException(400, "Плательщик должен быть участником группы")
    if not payload.participants:
        raise HTTPException(400, "Нужно выбрать хотя бы одного участника траты")

    participant_ids = [p.user_id for p in payload.participants]
    if any(uid not in member_ids for uid in participant_ids):
        raise HTTPException(400, "Все участники траты должны состоять в группе")
    if len(set(participant_ids)) != len(participant_ids):
        raise HTTPException(400, "Участник указан дважды")

    shares: dict[int, float] = {}
    if payload.split_type == "equal":
        n = len(payload.participants)
        base = round(payload.amount / n, ROUND)
        total_assigned = 0.0
        for i, p in enumerate(payload.participants):
            amt = base
            if i == n - 1:
                amt = round(payload.amount - total_assigned, ROUND)
            shares[p.user_id] = amt
            total_assigned += amt
    else:
        for p in payload.participants:
            if p.share_amount is None:
                raise HTTPException(400, "Для ручного разбиения укажите сумму каждому участнику")
            shares[p.user_id] = round(p.share_amount, ROUND)
        total = round(sum(shares.values()), ROUND)
        if abs(total - round(payload.amount, ROUND)) > EPS:
            raise HTTPException(400, f"Сумма долей ({total}) не равна сумме траты ({payload.amount})")

    expense = models.Expense(
        group_id=group_id,
        description=payload.description,
        amount=round(payload.amount, ROUND),
        paid_by_id=payload.paid_by_id,
        created_by_id=current_user.id,
    )
    db.add(expense)
    db.flush()

    for user_id, share_amount in shares.items():
        db.add(models.ExpenseShare(expense_id=expense.id, user_id=user_id, share_amount=share_amount))

    db.commit()
    db.refresh(expense)

    result = _expense_out(expense)

    await manager.broadcast(group_id, "expense_added", result.model_dump(mode="json"))
    balances = _balances_payload(db, group_id)
    await manager.broadcast(group_id, "balances_updated", balances.model_dump(mode="json"))

    return result


@router.get("", response_model=list[schemas.ExpenseOut])
def list_expenses(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_member(group_id, db, current_user)
    expenses = (
        db.query(models.Expense)
        .options(joinedload(models.Expense.shares).joinedload(models.ExpenseShare.user))
        .filter(models.Expense.group_id == group_id)
        .order_by(models.Expense.created_at.desc())
        .all()
    )
    return [_expense_out(e) for e in expenses]


balances_router = APIRouter(prefix="/api/groups/{group_id}/balances", tags=["balances"])


@balances_router.get("", response_model=schemas.GroupBalancesOut)
def get_balances(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_member(group_id, db, current_user)
    return _balances_payload(db, group_id)


analytics_router = APIRouter(prefix="/api/groups/{group_id}/analytics", tags=["analytics"])


@analytics_router.get("", response_model=schemas.GroupAnalyticsOut)
def get_analytics(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_member(group_id, db, current_user)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(404, "Группа не найдена")

    expenses = (
        db.query(models.Expense)
        .options(joinedload(models.Expense.shares))
        .filter(models.Expense.group_id == group_id)
        .all()
    )

    buckets: dict[str, dict[str, float]] = {}
    for expense in expenses:
        month = expense.created_at.strftime("%Y-%m")
        bucket = buckets.setdefault(month, {"group_total": 0.0, "my_total": 0.0})
        bucket["group_total"] += expense.amount
        for share in expense.shares:
            if share.user_id == current_user.id:
                bucket["my_total"] += share.share_amount

    months = [
        schemas.MonthlyStat(
            month=m,
            group_total=round(buckets[m]["group_total"], ROUND),
            my_total=round(buckets[m]["my_total"], ROUND),
        )
        for m in sorted(buckets.keys())
    ]

    return schemas.GroupAnalyticsOut(currency=group.currency, months=months)
