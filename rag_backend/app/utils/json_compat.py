from typing import Any, Union, Optional
import json

try:
    import orjson
    
    def dumps(obj: Any, default: Optional[Any] = None, option: Optional[int] = None) -> str:
        if option is not None:
            return orjson.dumps(obj, default=default, option=option).decode()
        elif default is not None:
            return orjson.dumps(obj, default=default).decode()
        else:
            return orjson.dumps(obj).decode()
    
    def loads(s: Union[str, bytes]) -> Any:
        return orjson.loads(s)
    
    def dump(obj: Any, fp: Any, default: Optional[Any] = None, option: Optional[int] = None, **kwargs) -> None:
        fp.write(dumps(obj, default=default, option=option))
    
    def load(fp: Any) -> Any:
        return loads(fp.read())
    
    __version__ = "orjson"
    
except ImportError:
    dumps = json.dumps
    loads = json.loads
    dump = json.dump
    load = json.load
    __version__ = "json"
