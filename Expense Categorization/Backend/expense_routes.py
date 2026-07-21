import os

from flask import Blueprint
from flask import request
from flask import jsonify

from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt_identity

from database import db
from models import Transaction

from pdf_parser import extract_pdf_text
from ai_categorizer import categorize_transactions

expense_bp = Blueprint(
    "expense",
    __name__
)


@expense_bp.route(
    "/upload",
    methods=["POST"]
)
@jwt_required()
def upload_statement():

    try:

        user_id = get_jwt_identity()

        file = request.files["file"]

        if not file:
            return jsonify({
                "error": "No file selected"
            }), 400

        UPLOAD_FOLDER = "uploads"

        os.makedirs(
            UPLOAD_FOLDER,
            exist_ok=True
        )

        filename = file.filename

        path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        file.save(path)

        print("PDF Saved Successfully")
        print("Path:", path)

        text = extract_pdf_text(path)

        print("\n===== EXTRACTED TEXT =====\n")
        print(text[:1000])

        categorized = categorize_transactions(
            text
        )

        print("\n===== CATEGORIZED RESULT =====\n")
        print(categorized)

        for item in categorized:

            txn = Transaction(
                user_id=user_id,
                description=item["description"],
                amount=item["amount"],
                category=item["category"]
            )

            db.session.add(txn)

        db.session.commit()

        return jsonify(categorized)

    except Exception as e:

        print("UPLOAD ERROR:", e)

        return jsonify({
            "error": str(e)
        }), 500


@expense_bp.route(
    "/analysis",
    methods=["GET"]
)
@jwt_required()
def analysis():

    user_id = get_jwt_identity()

    txns = Transaction.query.filter_by(
        user_id=user_id
    ).all()

    total = sum(
        txn.amount for txn in txns
    )

    result = {}

    for txn in txns:

        result.setdefault(
            txn.category,
            0
        )

        result[txn.category] += txn.amount

    percentages = {}

    if total > 0:

        for category, amount in result.items():

            percentages[category] = round(
                (amount / total) * 100,
                2
            )

    return jsonify({
        "total_expense": total,
        "category_breakdown": percentages
    })