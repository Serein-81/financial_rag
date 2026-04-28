import csv
import io
import json


def profile_table_text(table_text: str, delimiter: str = ",") -> str:
    """对 CSV 或分隔符文本做轻量质量概览。"""
    text = str(table_text or "").strip()
    if not text:
        return json.dumps({"错误": "表格文本为空"}, ensure_ascii=False)

    normalized_delimiter = "\t" if delimiter == "\\t" else delimiter
    reader = csv.reader(io.StringIO(text), delimiter=normalized_delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return json.dumps({"错误": "没有可解析的数据行"}, ensure_ascii=False)

    header = rows[0]
    data_rows = rows[1:]
    column_count = len(header)
    missing_by_column = {name or f"第{index + 1}列": 0 for index, name in enumerate(header)}
    duplicate_count = len(data_rows) - len({tuple(row) for row in data_rows})

    for row in data_rows:
        for index, column_name in enumerate(header):
            value = row[index].strip() if index < len(row) else ""
            if value == "":
                missing_by_column[column_name or f"第{index + 1}列"] += 1

    result = {
        "总行数": len(rows),
        "数据行数": len(data_rows),
        "列数": column_count,
        "字段": header,
        "重复数据行数": max(duplicate_count, 0),
        "各字段缺失值数量": missing_by_column,
        "质量提示": _build_quality_tip(data_rows, missing_by_column, duplicate_count),
    }
    return json.dumps(result, ensure_ascii=False)


def _build_quality_tip(data_rows: list[list[str]], missing_by_column: dict[str, int], duplicate_count: int) -> str:
    if not data_rows:
        return "只有表头，没有数据行。"
    if duplicate_count > 0:
        return "存在重复行，建议去重后再分析。"
    if any(count > 0 for count in missing_by_column.values()):
        return "存在缺失值，建议先确认缺失字段是否影响分析。"
    return "未发现明显缺失值或重复行，可进入下一步分析。"


SKILL_TOOLS = [
    {
        "name": "profile_table_text",
        "description": "对 CSV 或分隔符表格文本做轻量质量检查，输出行列数量、缺失值、重复行和字段概览。",
        "func": profile_table_text,
        "parameters": {
            "table_text": {
                "type": "string",
                "description": "CSV 或分隔符表格文本，第一行应为表头。",
                "required": True,
            },
            "delimiter": {
                "type": "string",
                "description": "字段分隔符，默认逗号；制表符可传入 \\t。",
                "required": False,
            },
        },
    }
]
