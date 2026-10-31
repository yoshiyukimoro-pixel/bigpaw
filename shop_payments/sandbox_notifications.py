"""Review-only, durable message drafts for BIG PAW dog-food Sandbox.

No email, LINE, supplier API, customer address, SMS, card details or network.
A successful local payment journal must be backed by Square-verified payment.
Drafts are keyed by (order, kind) to avoid duplicate notification *preparation*.
They never become "sent" automatically. Operator must review recipients,
tracking details and the message before a future sender is connected.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing

from .retail_catalog import load_sale_catalog
from .sandbox_connector import SandboxOrderStore

PAID_DRAFTS = (
    ("operator_new_order", "operator"),
    ("supplier_purchase_request", "supplier"),
    ("customer_order_confirmed", "customer"),
)
STAGE_DRAFTS = {
    "supplier_ordered": (("operator_supplier_ordered", "operator"),),
    "supplier_backorder": (
        ("operator_supplier_shortage", "operator"),
        ("customer_supplier_shortage", "customer"),
    ),
    "received_at_shop": (("operator_goods_received", "operator"),),
    "shipped": (("customer_shipment_notice", "customer"),),
    "refund_review": (("operator_refund_action_needed", "operator"),),
    "refunded": (("customer_refund_completed", "customer"),),
}
ALL_TYPES = {kind: audience for kind,audience in PAID_DRAFTS}
ALL_TYPES.update({kind:audience for group in STAGE_DRAFTS.values()
                 for kind,audience in group})


def install_notification_tables(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_notification_drafts (
          order_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          audience TEXT NOT NULL CHECK(audience IN ('operator','supplier','customer')),
          created_at INTEGER NOT NULL,
          PRIMARY KEY(order_id,kind)
        )
    """)


def enqueue_notification_group(conn, order_id: str, entries) -> None:
    """Call inside the SAME transaction as the corresponding manual stage."""
    for kind,audience in entries:
        if ALL_TYPES.get(kind)!=audience:
            raise ValueError("Unsupported draft notification kind")
        conn.execute(
            "INSERT OR IGNORE INTO food_notification_drafts "
            "(order_id,kind,audience,created_at) VALUES (?,?,?,?)",
            (order_id,kind,audience,int(time.time())),
        )


class SandboxNotificationDrafts:
    def __init__(self, store: SandboxOrderStore):
        self.store=store
        with closing(self._open()) as conn:
            install_notification_tables(conn)

    def _open(self):
        conn=sqlite3.connect(self.store.db_file,timeout=10,isolation_level=None)
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _snapshot(self, order_id):
        snapshot=self.store.paid_order_snapshot(order_id)
        if not snapshot or not snapshot.get("square_payment_id"):
            raise ValueError("Verified Square Sandbox payment required")
        catalog=load_sale_catalog()
        cart=snapshot.get("cart",{})
        if (not isinstance(cart,dict) or not cart or
                any(sku not in catalog or type(qty) is not int or not 1<=qty<=10
                    for sku,qty in cart.items())):
            raise ValueError("Bad SKU snapshot")
        return snapshot,catalog

    def sync_paid(self, order_id: str) -> int:
        """Manually create drafts after a Square-verified paid order.

        Future webhook handler may call this only after successful independent
        payment API reconciliation. No message dispatch is performed.
        """
        self._snapshot(order_id)
        with closing(self._open()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                before=conn.total_changes
                enqueue_notification_group(conn,order_id,PAID_DRAFTS)
                result=conn.total_changes-before
                conn.execute("COMMIT")
                return result
            except Exception:
                conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _details(snapshot,catalog):
        items=[]
        for sku,qty in sorted(snapshot["cart"].items()):
            product=catalog[sku]
            items.append(f"・{sku} {product.name} {product.size} ×{qty}")
        return "\n".join(items)

    def preview(self, order_id: str, kind: str) -> dict:
        """Renders only pre-queued drafts; no personal data or real recipients."""
        if kind not in ALL_TYPES:
            raise ValueError("Unknown draft kind")
        with closing(self._open()) as conn:
            row=conn.execute(
                "SELECT kind,audience,created_at FROM food_notification_drafts "
                "WHERE order_id=? AND kind=?", (order_id,kind),
            ).fetchone()
        if not row:
            raise ValueError("Draft has not been queued")
        snapshot,catalog=self._snapshot(order_id)
        items=self._details(snapshot,catalog)
        yen=f'{snapshot["amount_yen"]:,}円'
        common=f"ご注文番号：{order_id}\n{items}\n商品代金（税込・送料込み）：{yen}\n追加送料：0円"
        lead="通常、ご注文・決済完了から4〜7日程度がお届け目安です。休業日や配送事情により前後します。"
        templates={
            "operator_new_order": (
                "【BIG PAW・要対応】フード注文の決済確認",
                f"Square Sandboxで入金確認済みの注文が登録されました。\n{common}\n"
                "次の対応：九州のトランペッツへ在庫・納期確認と発注を行ってください。"
                " この通知は実際に送信されていない下書きです。"
            ),
            "supplier_purchase_request": (
                "【発注内容確認】BIG PAW ドッグフード",
                f"トランペッツご担当者様\n\n以下の商品の在庫・出荷可能日をご確認ください。\n"
                f"{items}\n\n埼玉県の当店宛てにお取り寄せ予定です。"
                "発注確定前に数量・納期・卸価格・送料の条件をご確認ください。"
                "\n\n※この文章は発注依頼の下書きであり、まだ発注されていません。"
            ),
            "customer_order_confirmed": (
                "【BIG PAW】ドッグフードご注文・決済確認",
                f"このたびはご注文ありがとうございます。\n{common}\n\n"
                "商品はご決済後に仕入先から当店（埼玉）へ取り寄せ、"
                "入荷・検品後に当店から発送いたします。\n"
                f"{lead}\n欠品の場合は速やかにご連絡し、"
                "入荷予定のご案内または全額返金にて対応いたします。"
            ),
            "operator_supplier_ordered": (
                "【BIG PAW・記録】仕入先への発注済み",
                f"{common}\n仕入先への発注済みとして手動記録されました。"
                "埼玉の当店への入荷予定と数量を確認してください。"
            ),
            "operator_supplier_shortage": (
                "【BIG PAW・至急確認】仕入先欠品",
                f"{common}\n仕入先で欠品が記録されています。"
                "お客様に速やかに連絡し、入荷待ちの可否・全額返金希望を確認してください。"
            ),
            "customer_supplier_shortage": (
                "【BIG PAW】ご注文商品の在庫・納期について",
                f"ご注文ありがとうございます。\nご注文番号：{order_id}\n"
                "仕入先にて商品の欠品が確認されました。ご迷惑をおかけし申し訳ございません。"
                "入荷予定をご案内のうえ、お待ちいただくか、全額返金をご希望か確認させてください。"
                "返金済みとの意味ではありません。"
            ),
            "operator_goods_received": (
                "【BIG PAW・要対応】当店への商品入荷・検品",
                f"{common}\n九州の仕入先から埼玉の当店への入荷・検品済みとして記録されました。"
                "実物と数量を再確認し、配送先と発送準備を確認してください。"
            ),
            "customer_shipment_notice": (
                "【BIG PAW】ドッグフード発送のお知らせ",
                f"ご注文番号：{order_id}\n当店から商品を発送しました。\n"
                "配送会社：【運営が確認して入力】\n追跡番号：【運営が確認して入力】\n"
                "※運営が実際の引き渡しと配送先を確認してから送信してください。"
            ),
            "operator_refund_action_needed": (
                "【BIG PAW・要対応】返金手続きの確認",
                f"{common}\n注文の返金検討として記録されています。"
                "Squareでの全額返金はまだ実行・確認されていません。"
                "返金する場合は承認後に別途実施し、Squareの返金状態を照合してください。"
            ),
            "customer_refund_completed": (
                "【BIG PAW】ご注文商品の全額返金について",
                f"ご注文番号：{order_id}\n"
                f"Squareにて{yen}の全額返金が確認されました。"
                "カード会社の処理状況により、明細への反映には時間がかかる場合があります。"
            ),
        }
        subject,body=templates[kind]
        return {
            "order_id":order_id,"kind":kind,"audience":row["audience"],
            "subject":subject,"body":body,"status":"draft_not_sent",
            "created_at":row["created_at"],
            "recipient_address":None,"requires_manual_approval":True,
        }

    def pending(self, order_id: str | None = None) -> list[dict]:
        with closing(self._open()) as conn:
            if order_id is None:
                rows=conn.execute(
                    "SELECT order_id,kind FROM food_notification_drafts "
                    "ORDER BY created_at,order_id,kind").fetchall()
            else:
                rows=conn.execute(
                    "SELECT order_id,kind FROM food_notification_drafts "
                    "WHERE order_id=? ORDER BY created_at,kind",(order_id,)
                ).fetchall()
        return [self.preview(row["order_id"],row["kind"]) for row in rows]
