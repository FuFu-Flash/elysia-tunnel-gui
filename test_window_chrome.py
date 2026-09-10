"""Exercise real Windows caption setters without relying on unsupported getters."""
import ctypes,tempfile
from pathlib import Path
from PySide6.QtTest import QTest
from qt_ui import create_application,THEMES,read_preferences
with tempfile.TemporaryDirectory() as temp:
 app,engine,c,w=create_application(Path(temp)/'prefs.json')
 try:
  assert w.chrome.supported
  original=w.chrome.dwm.DwmSetWindowAttribute
  calls=[]
  def record(hwnd,attribute,pointer,size):
   result=original(hwnd,attribute,pointer,size)
   calls.append((attribute,ctypes.cast(pointer,ctypes.POINTER(ctypes.c_uint32)).contents.value,result))
   return result
  w.chrome.dwm.DwmSetWindowAttribute=record
  colors=[]
  for theme in THEMES:
   c.setPreference('theme',theme);w.chrome.update(force=True);QTest.qWait(30)
   assert calls[-2][0]==35 and calls[-1][0]==36
   assert calls[-2][2]==0 and calls[-1][2]==0
   colors.append(calls[-2][1])
  assert len(set(colors))==5
  w.showMaximized();w.showNormal();c.resetPreferences();QTest.qWait(50)
  assert w.chrome.last_color==colors[0]
  c.save();assert read_preferences(c.preference_path)['theme']=='爱莉粉'
  print('PASS five real DWM caption/text setters, maximize/restore, reset and persistence')
 finally:
  c.close();w.close();app.processEvents()
