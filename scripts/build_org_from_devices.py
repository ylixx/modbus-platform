"""用设备的 factory/production_line/workshop/installation 重建组织架构树并挂接设备。

层级映射：
  factory         -> node_type=factory (厂区)
  production_line -> node_type=team    (班)
  workshop        -> node_type=area    (站)
  installation     -> node_type=location(位置)

逻辑：
  1. 清空现有 org_nodes（演示桩树，已做 DB 备份；role_org_scopes=0，无权限影响）。
  2. 按 厂区→班→站→位置 逐级 find-or-create OrgNode，把每台设备挂到最后的「位置」叶子节点。
  3. 幂等：重跑结果一致。

运行：backend/.venv/Scripts/python.exe scripts/build_org_from_devices.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core.database import SessionLocal
from app.models.device import Device
from app.models.org import OrgNode

# (设备字段, OrgNode.node_type) 顺序即树深度
LEVELS = [
    ("factory", "factory"),
    ("production_line", "team"),
    ("workshop", "area"),
    ("installation", "location"),
]


def main():
    db = SessionLocal()
    try:
        # 1) 清空旧组织架构（含子节点，FK ondelete=CASCADE）
        db.query(OrgNode).delete()
        db.commit()

        cache = {}

        def get_node(name, node_type, parent_id):
            key = (parent_id, node_type, name)
            if key in cache:
                return cache[key]
            node = (
                db.query(OrgNode)
                .filter(
                    OrgNode.parent_id == parent_id,
                    OrgNode.node_type == node_type,
                    OrgNode.name == name,
                )
                .first()
            )
            if node is None:
                node = OrgNode(name=name, node_type=node_type, parent_id=parent_id)
                db.add(node)
                db.flush()
            cache[key] = node
            return node

        devices = db.query(Device).order_by(Device.id).all()
        linked = 0
        for d in devices:
            parent = None
            for field, ntype in LEVELS:
                val = getattr(d, field) or ""
                if not val:
                    val = f"未设置{ntype}"
                parent = get_node(val, ntype, parent.id if parent else None)
            d.org_node_id = parent.id
            linked += 1
        db.commit()

        total_nodes = db.query(OrgNode).count()
        print(f"已链接 {linked} 台设备；组织架构节点总数={total_nodes}")

        # 打印树结构用于核对
        all_nodes = db.query(OrgNode).all()
        by_parent = {}
        for n in all_nodes:
            by_parent.setdefault(n.parent_id, []).append(n)

        def print_tree(pid, depth):
            for n in sorted(by_parent.get(pid, []), key=lambda x: x.id):
                cnt = db.query(Device).filter(Device.org_node_id == n.id).count()
                print("  " * depth + f"- {n.name} [{n.node_type}] 设备={cnt}")
                print_tree(n.id, depth + 1)

        print_tree(None, 0)
    finally:
        db.close()


if __name__ == "__main__":
    main()
