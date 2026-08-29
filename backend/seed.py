"""Наполняет базу тестовыми пользователями и тратами, чтобы можно было
опробовать приложение сразу с несколькими участниками.

Запуск (из папки backend, при остановленном сервере):
    .\\venv\\Scripts\\python.exe seed.py
"""

from app.database import Base, SessionLocal, engine
from app import models
from app.security import hash_password

TEST_USERS = [
    ("anna", "password123"),
    ("boris", "password123"),
    ("viktor", "password123"),
]

TEST_PASSWORD_NOTE = "Пароль у всех тестовых пользователей: password123"


def get_or_create_user(db, username, password):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return user
    user = models.User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    test_users = [get_or_create_user(db, username, password) for username, password in TEST_USERS]

    real_user = db.query(models.User).order_by(models.User.id).first()
    group = db.query(models.Group).order_by(models.Group.id).first()

    if group is None:
        owner = real_user or test_users[0]
        group = models.Group(name="Сочи 2025", owner_id=owner.id)
        db.add(group)
        db.flush()

    all_members = test_users + ([real_user] if real_user else [])
    for u in all_members:
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
        anna, boris, viktor = test_users

        def add_expense(description, amount, paid_by, participants):
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

        participants_all = test_users + ([real_user] if real_user else [])
        add_expense("Ужин в кафе", 3200, anna, participants_all)
        add_expense("Такси в аэропорт", 950, boris, [boris, viktor])
        add_expense("Аренда квартиры", 12000, viktor, participants_all)
        db.commit()

    print(f"Группа: «{group.name}» (id={group.id}), код приглашения: {group.invite_code}")
    print("Тестовые пользователи добавлены в группу:")
    for username, password in TEST_USERS:
        print(f"  логин: {username:<8} пароль: {password}")
    if real_user:
        print(f"Ваш аккаунт «{real_user.username}» тоже состоит в этой группе.")
    print(f"Ссылка на группу: http://127.0.0.1:8000/index.html?join={group.invite_code}")


if __name__ == "__main__":
    main()
