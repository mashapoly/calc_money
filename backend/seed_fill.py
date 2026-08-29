"""Добавляет тестовых участников (anna/boris/viktor) и пару трат во все
группы владельца, где кроме него самого никого больше нет.

Запуск (из backend, сервер может быть запущен параллельно):
    .\\venv\\Scripts\\python.exe seed_fill.py
"""

from app.database import Base, SessionLocal, engine
from app import models
from app.security import hash_password

TEST_USERS = [
    ("anna", "password123"),
    ("boris", "password123"),
    ("viktor", "password123"),
]


def get_or_create_user(db, username, password):
    u = db.query(models.User).filter(models.User.username == username).first()
    if u:
        return u
    u = models.User(username=username, password_hash=hash_password(password))
    db.add(u)
    db.flush()
    return u


def add_expense(db, group, description, amount, paid_by, participants):
    expense = models.Expense(
        group_id=group.id,
        description=description,
        amount=amount,
        paid_by_id=paid_by.id,
        created_by_id=paid_by.id,
    )
    db.add(expense)
    db.flush()
    share = round(amount / len(participants), 2)
    total = 0
    for i, p in enumerate(participants):
        amt = share if i < len(participants) - 1 else round(amount - total, 2)
        db.add(models.ExpenseShare(expense_id=expense.id, user_id=p.id, share_amount=amt))
        total += amt


SAMPLE_EXPENSES = [
    ("Продукты", 4200, 0, [0, 1, 2, 3]),
    ("Бензин", 2600, 1, [1, 2]),
    ("Кафе", 1800, 2, [0, 2, 3]),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    test_users = [get_or_create_user(db, username, password) for username, password in TEST_USERS]
    db.commit()

    groups = db.query(models.Group).all()

    for group in groups:
        member_count = (
            db.query(models.GroupMember).filter(models.GroupMember.group_id == group.id).count()
        )
        if member_count > 1:
            continue  # already has extra participants (e.g. the first seeded group)

        owner = db.query(models.User).filter(models.User.id == group.owner_id).first()
        roster = [owner] + test_users

        for u in test_users:
            exists = (
                db.query(models.GroupMember)
                .filter(models.GroupMember.group_id == group.id, models.GroupMember.user_id == u.id)
                .first()
            )
            if not exists:
                db.add(models.GroupMember(group_id=group.id, user_id=u.id))
        db.commit()

        has_expenses = db.query(models.Expense).filter(models.Expense.group_id == group.id).first()
        if not has_expenses:
            for description, amount, payer_idx, participant_idxs in SAMPLE_EXPENSES:
                payer = roster[payer_idx]
                participants = [roster[i] for i in participant_idxs]
                add_expense(db, group, description, amount, payer, participants)
            db.commit()

        print(f"Группа id={group.id} «{group.name}»: добавлены anna/boris/viktor + примеры трат")


if __name__ == "__main__":
    main()
