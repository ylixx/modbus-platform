"""Batch import API — devices and tags from CSV/Excel."""
import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.services.import_service import import_devices_csv, import_tags_csv

router = APIRouter(prefix="/import", tags=["批量导入"])


@router.post("/devices")
async def import_devices(
    file: UploadFile = File(...),
    _: User = Depends(require_permission("import.write")),
):
    """Import devices from CSV file."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过5MB限制")
    result = import_devices_csv(content)
    return {
        "message": f"导入完成：成功 {result['created']} 条",
        "created": result["created"],
        "errors": result["errors"],
    }


@router.post("/tags")
async def import_tags(
    file: UploadFile = File(...),
    _: User = Depends(require_permission("import.write")),
):
    """Import tags from CSV file."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过5MB限制")
    result = import_tags_csv(content)
    return {
        "message": f"导入完成：成功 {result['created']} 条",
        "created": result["created"],
        "errors": result["errors"],
    }


@router.get("/template/devices")
def download_device_template(_: User = Depends(require_permission("import.read"))):
    """Download device import CSV template."""
    csv_content = "name,protocol,host,port,slave_id,poll_interval,factory,workshop,production_line,installation,description\n"
    csv_content += "示例设备1,modbus_tcp,127.0.0.1,502,1,5,一号厂级,A区级,1号线,3号机组,示例设备\n"
    csv_content += "示例设备2,mqtt,192.168.1.101,1883,,10,一号厂级,B区级,,,MQTT示例\n"
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="device_template.csv"'},
    )


@router.get("/template/tags")
def download_tag_template(_: User = Depends(require_permission("import.read"))):
    """Download tag import CSV template."""
    csv_content = "device_name,name,function_code,address,data_type,byte_order,scale_factor,offset,decimal_places,unit,writable,description\n"
    csv_content += "示例设备1,temperature,holding_register,0,float32,big_endian,0.1,0,2,°C,false,温度\n"
    csv_content += "示例设备1,humidity,holding_register,2,float32,big_endian,0.1,0,2,%,false,湿度\n"
    csv_content += "示例设备1,alarm_flag,coil,0,bool,big_endian,1,0,0,,false,报警标志\n"
    csv_content += "示例设备1,setpoint,holding_register,10,int16,big_endian,1,0,0,°C,true,设定值\n"
    return Response(
        content="\ufeff" + csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tag_template.csv"'},
    )
