"""
This file contains the `Config` class which basically deals with 
each user's settings, preferences & app-specific info
"""

import json
import os
import sys


    
class Config:
    def __init__(self, cfg_path=".local/config.json"):
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.path = os.path.join(self.base_dir, cfg_path)
        
        self.data: dict
        with open(self.path, "r", encoding="utf-8") as cfg:
            self.data = json.load(cfg)
        
    def get(self, category: str, varname: str):
        value = self.data.get(category, {}).get(varname, {}).get("value", None)
        if value is not None:
            if category == "path":
                return os.path.join(self.base_dir, value)
            else:
                return value
        else:
            return None
    
    def set(self, category: str, varname: str, value):
        if self.data.get(category, {}).get(varname) is not None:
            self.data[category][varname]["value"] = value
            self._save()
    
    def _save(self):
        with open(self.path, "w", encoding="utf-8") as cfg:
            json.dump(self.data, cfg, indent=4)
            
    
    def get_var_struct(self, category: str, varname: str) -> dict | None:
        return self.data.get(category, {}).get(varname)


    
"""
Use this variable anywhere else to prevent reloading config.json every time
"""     
APP_CONFIG = Config()
            
    