"""
This file contains the `Config` class which basically deals with 
each user's settings, preferences & app-specific info
"""

import json

class Config:
    def __init__(self, cfg_path=".local/config.json"):
        self.path = cfg_path
        self.data: dict
        with open(self.path, "r", encoding="utf-8") as cfg:
            self.data = json.load(cfg)
            
    def get(self, category: str, var: str):
        return self.data.get(category, {}).get(var)
    
    def set(self, category: str, var: str, value):
        if category not in self.data:
            self.data[category] = {}
        self.data[category][var] = value
        self._save()
    
    def _save(self):
        with open(self.path, "w", encoding="utf-8") as cfg:
            json.dump(self.data, cfg, indent=4)
            

"""
Use this variable anywhere else to prevent reloading config.json every time
"""     
APP_CONFIG = Config()
            
    