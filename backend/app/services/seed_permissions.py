"""Seed default permissions and roles."""
from loguru import logger
from app.core.database import SessionLocal
from app.models.permission import Permission, Role, RolePermission


DEFAULT_PERMISSIONS = [
    # Device module
    ("device.read",    "查看设备",     "device",   "查看设备列表和详情"),
    ("device.write",   "编辑设备",     "device",   "创建/修改/删除设备"),
    ("device.control", "远程控制",     "device",   "向设备写入值"),
    ("tag.read",       "查看点位",     "device",   "查看采集点位"),
    ("tag.write",      "编辑点位",     "device",   "创建/修改/删除采集点位"),
    ("group.read",     "查看分组",     "device",   "查看设备分组"),
    ("group.write",    "编辑分组",     "device",   "创建/修改/删除分组"),

    # Alarm module
    ("alarm.read",     "查看报警",     "alarm",    "查看报警规则和记录"),
    ("alarm.write",    "编辑报警规则", "alarm",    "创建/修改/删除报警规则"),
    ("alarm.ack",      "确认报警",     "alarm",    "确认活跃报警"),
    ("alarm.clear",    "消除报警",     "alarm",    "手动消除报警"),

    # SMS module
    ("sms.read",       "查看短信",     "sms",      "查看联系人/规则/记录"),
    ("sms.write",      "编辑短信配置", "sms",      "管理联系人和推送规则"),
    ("sms.send",       "发送短信",     "sms",      "发送测试短信"),

    # History & Export
    ("history.read",   "查看历史数据", "history",  "查询历史趋势"),
    ("export.download","导出数据",     "export",   "下载CSV/报表"),

    # System
    ("user.read",      "查看用户",     "system",   "查看用户列表"),
    ("user.write",     "管理用户",     "system",   "创建/修改/删除用户"),
    ("rbac.read",      "查看权限",     "system",   "查看角色和权限配置"),
    ("rbac.write",     "管理权限",     "system",   "管理角色/权限分配"),
    ("audit.read",     "查看审计日志", "system",   "查看操作审计日志"),
    ("system.admin",   "系统管理",     "system",   "完全管理权限"),

    # Config & SCADA
    ("config.read",    "查看配置",     "config",   "查看系统/采集配置"),
    ("config.write",   "编辑配置",     "config",   "修改系统/采集配置"),
    ("scada.read",     "查看SCADA",    "scada",    "查看SCADA页面与组件"),
    ("scada.write",    "编辑SCADA",    "scada",    "创建/修改/删除SCADA页面与组件"),

    # Scripts
    ("script.read",    "查看脚本",     "script",   "查看数据处理脚本"),
    ("script.write",   "编辑脚本",     "script",   "创建/修改/删除/测试脚本"),

    # Imports
    ("import.read",    "查看导入模板", "import",   "下载设备/点位导入模板"),
    ("import.write",   "执行导入",     "import",   "导入设备/点位数据"),

    # Hierarchy
    ("hierarchy.read","查看层级配置", "hierarchy","查看组织层级配置与树"),
    ("hierarchy.write","编辑层级配置", "hierarchy","创建/修改/删除层级配置"),

    # Organization
    ("org.read",       "查看组织架构", "org",      "查看组织架构树（厂-区-班组-位置）"),
    ("org.write",      "编辑组织架构", "org",      "创建/修改/删除组织节点、调整设备归属"),

    # Templates
    ("template.read",  "查看模板",     "template", "查看设备/报警规则模板"),
    ("template.write", "从模板创建",   "template", "基于模板创建设备"),

    # Dashboard
    ("dashboard.read", "查看仪表盘",   "dashboard","查看概览/状态/趋势"),
]


DEFAULT_ROLES = [
    {
        "code": "admin",
        "name": "系统管理员",
        "description": "拥有全部权限",
        "is_system": True,
        "permissions": ["*"],  # all
    },
    {
        "code": "engineer",
        "name": "工程师",
        "description": "设备配置、报警管理、数据查看",
        "is_system": True,
        "permissions": [
            "device.read", "device.write", "device.control",
            "tag.read", "tag.write", "group.read", "group.write",
            "alarm.read", "alarm.write", "alarm.ack", "alarm.clear",
            "sms.read", "sms.write",
            "history.read", "export.download",
            "config.read", "config.write",
            "scada.read", "scada.write",
            "script.read", "script.write",
            "import.read", "import.write",
            "hierarchy.read", "hierarchy.write",
            "org.read", "org.write",
            "template.read", "template.write",
            "dashboard.read",
        ],
    },
    {
        "code": "operator",
        "name": "操作员",
        "description": "日常操作：查看设备、确认报警、远程控制",
        "is_system": True,
        "permissions": [
            "device.read", "device.control",
            "tag.read", "group.read",
            "alarm.read", "alarm.ack", "alarm.clear",
            "history.read",
            "config.read", "scada.read", "script.read",
            "import.read", "hierarchy.read", "org.read", "template.read",
            "dashboard.read",
        ],
    },
    {
        "code": "viewer",
        "name": "观察者",
        "description": "只读权限：查看设备、报警、历史数据",
        "is_system": True,
        "permissions": [
            "device.read", "tag.read", "group.read",
            "alarm.read",
            "history.read",
            "config.read", "scada.read", "script.read",
            "import.read", "hierarchy.read", "org.read", "template.read",
            "dashboard.read",
        ],
    },
]


def seed_permissions():
    """Create default permissions and roles if not exist."""
    db = SessionLocal()
    try:
        # Seed permissions
        perm_map = {}
        for code, name, module, desc in DEFAULT_PERMISSIONS:
            perm = db.query(Permission).filter(Permission.code == code).first()
            if not perm:
                perm = Permission(code=code, name=name, module=module, description=desc)
                db.add(perm)
                db.flush()
            perm_map[code] = perm

        # Seed roles (and backfill new permission codes for existing system roles)
        for role_def in DEFAULT_ROLES:
            role = db.query(Role).filter(Role.code == role_def["code"]).first()
            if not role:
                role = Role(
                    code=role_def["code"], name=role_def["name"],
                    description=role_def["description"], is_system=role_def["is_system"],
                )
                db.add(role)
                db.flush()

            # Sync permissions: add any missing default permission to system roles
            existing_pids = {
                rp.permission_id
                for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
            }
            wanted = []
            for perm_code in role_def["permissions"]:
                if perm_code == "*":
                    wanted = list(perm_map.values())
                    break
                if perm_code in perm_map:
                    wanted.append(perm_map[perm_code])
            for p in wanted:
                if p.id not in existing_pids:
                    db.add(RolePermission(role_id=role.id, permission_id=p.id))

        db.commit()
        logger.info("Default permissions and roles seeded")
    except Exception as e:
        logger.error(f"Seed permissions error: {e}")
        db.rollback()
    finally:
        db.close()
