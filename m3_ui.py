"""Tkinter Material 3 controls; standard library only."""
import math
import time
import tkinter as tk

BG = '#F8F5FC'
SURFACE = '#FFFBFF'
PRIMARY = '#6750A4'
TEXT = '#211D29'
MUTED = '#71697D'
TONAL = '#ECE3FA'
FONT = ('Microsoft YaHei UI', -14)
MOTION = True
MOTION_DURATION_SCALE = 2.0


def status_copy(value):
    messages = {
        '准备就绪': '准备好啦，要和我一起出发吗？♪',
        '已连接': '连接成功啦，去和世界打个招呼吧♪',
        '已停止': '已经停好啦，想出发时再叫我哦。',
        '连接失败': '哎呀，连接失败了，我们看看日志吧。',
        '正在停止…': '正在停止连接，稍等我一下哦…',
        '检测本地服务…': '让我看看，你的本地服务准备好了吗？',
        '正在获取官方内核…': '先准备好官方内核，我们就能出发啦♪',
        '隧道已连接 · 本地服务不可用': '隧道还在哦，请先恢复本地服务。',
    }
    if value in messages:
        return messages[value]
    if value.startswith('正在连接 '):
        return value.rstrip('…') + '，稍等我一下哦…'
    if value.startswith('下载内核 '):
        return '正在准备连接的小帮手 · ' + value
    if value.startswith('连接中断，'):
        return '别着急哦，' + value
    return value


def mix(a, b, amount):
    amount = max(0, min(1, amount))
    return '#' + ''.join(f'{round(int(a[i:i+2],16)*(1-amount)+int(b[i:i+2],16)*amount):02x}' for i in (1, 3, 5))


def outline(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    points = []
    for cx, cy, start in ((x+w-r, y+r, -90), (x+w-r, y+h-r, 0),
                          (x+r, y+h-r, 90), (x+r, y+r, 180)):
        for step in range(13):
            angle = math.radians(start + step * 90 / 12)
            points.append((cx+r*math.cos(angle), cy+r*math.sin(angle)))
    return points


def rounded(canvas, x, y, w, h, radius, color, **kw):
    return canvas.create_polygon(*[v for p in outline(x,y,max(1,w),max(1,h),radius) for v in p],
                                 fill=color, outline='', **kw)


def clip_polygon(subject, boundary):
    # Clip the ripple to the rounded button, including the corner pixels.
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        if not subject:
            break
        result = []
        def side(p):
            return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        previous = subject[-1]
        d0 = side(previous)
        for current in subject:
            d1 = side(current)
            if (d0 >= 0) != (d1 >= 0):
                t = d0 / (d0-d1)
                result.append((previous[0]+t*(current[0]-previous[0]),
                               previous[1]+t*(current[1]-previous[1])))
            if d1 >= 0:
                result.append(current)
            previous, d0 = current, d1
        subject = result
    return subject


class AnimatedCanvas(tk.Canvas):
    def __init__(self, master, **kw):
        super().__init__(master, bd=0, highlightthickness=0, **kw)
        self.jobs = {}
        self.bind('<Destroy>', self._destroy, add='+')

    def later(self, key, delay, callback):
        old = self.jobs.pop(key, None)
        if old:
            self.after_cancel(old)
        def run():
            self.jobs.pop(key, None)
            if self.winfo_exists():
                callback()
        self.jobs[key] = self.after(delay, run)

    def animate(self, key, duration, update, done=None):
        duration *= MOTION_DURATION_SCALE
        started = time.monotonic()
        def step():
            t = min(1, (time.monotonic()-started) / duration) if MOTION else 1
            update(1-(1-t)**3)
            if t < 1:
                self.later(key, 16, step)
            elif done:
                done()
        old = self.jobs.pop(key, None)
        if old:
            self.after_cancel(old)
        step()

    def _destroy(self, event):
        if event.widget is self:
            for job in list(self.jobs.values()):
                self.after_cancel(job)
            self.jobs.clear()


class Surface(AnimatedCanvas):
    def __init__(self, master, color=SURFACE, radius=28, padding=24,
                 stretch=False, **kw):
        super().__init__(master, bg=master.cget('bg'), **kw)
        self.color, self.radius, self.padding = color, radius, padding
        self.stretch = stretch
        self.body = tk.Frame(self, bg=color)
        self.window = self.create_window(padding, padding, window=self.body, anchor='nw')
        self.bind('<Configure>', self.layout)
        self.body.bind('<Configure>', self.layout)

    def layout(self, event=None):
        w = max(1, self.winfo_width())
        p = self.padding
        self.itemconfigure(self.window, width=max(1, w-2*p))
        if self.stretch:
            self.itemconfigure(self.window, height=max(1, self.winfo_height()-2*p-3))
        else:
            desired = self.body.winfo_reqheight()+2*p+3
            if int(self.cget('height')) != desired:
                self.configure(height=desired)
        h = self.winfo_height()
        self.delete('surface')
        rounded(self, 1, 3, w-2, h-3, self.radius, '#E8E1F0', tags='surface')
        rounded(self, 0, 0, w, h-3, self.radius, self.color, tags='surface')
        self.tag_lower('surface')


class Button(AnimatedCanvas):
    def __init__(self, master, text, command=None, variant='tonal',
                 state='normal', width=120, height=46, **kw):
        super().__init__(master, bg=master.cget('bg'), width=width, height=height,
                         takefocus=1, cursor='hand2', **kw)
        self.text, self.command, self.variant = text, command, variant
        self.control_state = state
        self.hover = 0.0
        self.focused = False
        self.pressed = False
        self.ripple = None
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_hover(1))
        self.bind('<Leave>', lambda e: self.set_hover(0))
        self.bind('<FocusIn>', lambda e: self.set_focus(True))
        self.bind('<FocusOut>', lambda e: self.set_focus(False))
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<space>', self.keyboard)
        self.bind('<Return>', self.keyboard)

    def configure(self, cnf=None, **kw):
        if 'state' in kw:
            self.control_state = kw.pop('state')
            self.pressed = False
        if 'text' in kw:
            self.text = kw.pop('text')
        result = super().configure(cnf, **kw)
        if hasattr(self, 'hover'):
            self.draw()
        return result

    config = configure

    def set_focus(self, focused):
        self.focused = focused
        self.draw()

    def set_hover(self, target):
        initial = self.hover
        self.animate('hover', .18, lambda t: self.paint_hover(initial+(target-initial)*t))

    def paint_hover(self, value):
        self.hover = value
        self.draw()

    def press(self, event):
        if self.control_state == 'disabled':
            return
        self.focus_set()
        self.pressed = True
        x, y = event.x, event.y
        self.animate('ripple', .46, lambda t: self.paint_ripple(x,y,t), self.end_ripple)

    def paint_ripple(self, x, y, t):
        self.ripple = (x, y, t)
        self.draw()

    def end_ripple(self):
        self.ripple = None
        self.draw()

    def release(self, event):
        pressed = self.pressed
        self.pressed = False
        if pressed and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def keyboard(self, event):
        if self.control_state != 'disabled':
            self.animate('ripple', .46,
                         lambda t: self.paint_ripple(self.winfo_width()/2,self.winfo_height()/2,t),
                         self.end_ripple)
            self.invoke()
        return 'break'

    def invoke(self):
        if self.control_state != 'disabled' and self.command:
            self.command()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        disabled = self.control_state == 'disabled'
        base = PRIMARY if self.variant == 'filled' else TONAL
        ink = '#FFFFFF' if self.variant == 'filled' else '#4F378B'
        if self.variant == 'text':
            base = self.cget('bg')
        if disabled:
            base, ink = '#ECE8EF', '#A8A1AF'
        else:
            base = mix(base, ink, self.hover*.09)
        if self.focused and not disabled:
            rounded(self, 0, 0, w, h, h/2, '#B69BDC')
        boundary = outline(3,3,max(1,w-6),max(1,h-6),(h-6)/2)
        rounded(self, 3, 3, w-6, h-6, (h-6)/2, base)
        if self.ripple and not disabled:
            x,y,t = self.ripple
            r = math.hypot(w,h)*t
            points = [(x+r*math.cos(i*math.tau/48),y+r*math.sin(i*math.tau/48)) for i in range(48)]
            points = clip_polygon(points, boundary)
            if len(points) >= 3:
                self.create_polygon(*[v for p in points for v in p],
                                    fill=mix(base,ink,.20*(1-t)),outline='')
        self.create_text(w/2,h/2,text=self.text,fill=ink,font=FONT)
        super().configure(cursor='arrow' if disabled else 'hand2')


class Segments(AnimatedCanvas):
    def __init__(self, master, variable, values, command=None, width=300):
        super().__init__(master, bg=master.cget('bg'), width=width, height=46,
                         takefocus=1, cursor='hand2')
        self.variable, self.values, self.command = variable, list(values), command
        self.control_state = 'normal'
        self.position = float(self.index())
        self.hover = -1
        self.focused = False
        self.trace = variable.trace_add('write', self.changed)
        self.bind('<Destroy>', self.remove_trace, add='+')
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Motion>', self.motion)
        self.bind('<Leave>', lambda e: self.motion(None))
        self.bind('<Button-1>', self.click)
        self.bind('<Left>', lambda e: self.select(self.index()-1))
        self.bind('<Right>', lambda e: self.select(self.index()+1))
        self.bind('<Home>', lambda e: self.select(0))
        self.bind('<End>', lambda e: self.select(len(self.values)-1))
        self.bind('<FocusIn>', lambda e: self.focus(True))
        self.bind('<FocusOut>', lambda e: self.focus(False))

    def index(self):
        try:
            return self.values.index(self.variable.get())
        except ValueError:
            return 0

    def remove_trace(self, event):
        if event.widget is self:
            self.variable.trace_remove('write', self.trace)

    def configure(self, cnf=None, **kw):
        if 'state' in kw:
            self.control_state = kw.pop('state')
        result = super().configure(cnf, **kw)
        if hasattr(self, 'position'):
            self.draw()
        return result

    config = configure

    def focus(self, value):
        self.focused = value
        self.draw()

    def motion(self, event):
        self.hover = min(len(self.values)-1,int(event.x/max(1,self.winfo_width())*len(self.values))) if event else -1
        self.draw()

    def click(self, event):
        self.focus_set()
        self.select(int(event.x/max(1,self.winfo_width())*len(self.values)))

    def select(self, index):
        if self.control_state != 'disabled':
            self.variable.set(self.values[max(0,min(index,len(self.values)-1))])
        return 'break'

    def changed(self, *args):
        initial, target = self.position, self.index()
        self.animate('selection', .25, lambda t: self.move(initial+(target-initial)*t))
        if self.command:
            self.command(self.variable.get())

    def move(self, value):
        self.position = value
        self.draw()

    def draw(self):
        self.delete('all')
        w,h = self.winfo_width(),self.winfo_height()
        disabled = self.control_state == 'disabled'
        rounded(self,0,0,w,h,h/2,'#B69BDC' if self.focused and not disabled else '#E9E3EF')
        rounded(self,1,1,w-2,h-2,h/2,'#F3EEF7')
        cell = (w-8)/len(self.values)
        if self.hover >= 0 and not disabled:
            rounded(self,4+self.hover*cell,4,cell,h-8,19,'#EDE5F6')
        rounded(self,4+self.position*cell,4,cell,h-8,19,'#E4D6F6' if not disabled else '#E5E0E9')
        for i,value in enumerate(self.values):
            self.create_text(4+(i+.5)*cell,h/2,text=value,
                             fill='#AAA1B3' if disabled else PRIMARY if i==self.index() else MUTED,
                             font=('Microsoft YaHei UI',-13,'bold') if i==self.index() else ('Microsoft YaHei UI',-13))


class Field(AnimatedCanvas):
    def __init__(self, master, variable, label='', state='normal', show='', width=200, dropdown=False):
        super().__init__(master, bg=master.cget('bg'), width=width, height=62)
        self.variable, self.label = variable, label
        self.control_state, self.values = state, []
        self.dropdown = dropdown
        self.menu = None
        self.focus_amount = 0.
        self.entry = tk.Entry(self,textvariable=variable,show=show,bd=0,relief='flat',
                              font=('Microsoft YaHei UI',-15),fg=TEXT,bg='#F5F0F9',
                              readonlybackground='#F5F0F9',disabledbackground='#F0EBF3',
                              disabledforeground='#A59DAF',insertbackground=PRIMARY,
                              selectbackground='#E2D3F5',highlightthickness=0,state=state)
        self.window = self.create_window(17,31,anchor='w',window=self.entry)
        self.bind('<Configure>', lambda e: self.draw())
        self.entry.bind('<FocusIn>', lambda e: self.focus(1))
        self.entry.bind('<FocusOut>', lambda e: self.focus(0))
        self.entry.bind('<Down>', lambda e: self.popup())
        self.entry.bind('<Alt-Down>', lambda e: self.popup())
        self.bind('<Button-1>',self.click)

    def configure(self, cnf=None, **kw):
        if 'values' in kw:
            self.values = list(kw.pop('values'))
        if 'state' in kw:
            self.control_state = kw.pop('state')
            if hasattr(self,'entry'):
                self.entry.configure(state=self.control_state)
        result = super().configure(cnf,**kw)
        if hasattr(self,'entry'):
            self.draw()
        return result

    config = configure

    def focus(self, target):
        initial = self.focus_amount
        self.animate('focus', .18, lambda t: self.paint_focus(initial+(target-initial)*t))

    def paint_focus(self, value):
        self.focus_amount = value
        self.draw()

    def click(self, event):
        if self.control_state != 'disabled':
            if self.dropdown and event.x > self.winfo_width()-40:
                self.popup()
            else:
                self.entry.focus_set()

    def popup(self):
        if self.control_state == 'disabled' or not self.values:
            return 'break'
        if self.menu is None:
            self.menu = tk.Menu(self,tearoff=False,font=FONT,bg=SURFACE,fg=TEXT,
                                activebackground=TONAL,activeforeground=PRIMARY)
        menu = self.menu
        menu.delete(0,'end')
        for value in self.values:
            menu.add_command(label=str(value),command=lambda v=value:self.variable.set(v))
        try:
            menu.tk_popup(self.winfo_rootx(),self.winfo_rooty()+self.winfo_height())
        finally:
            menu.grab_release()
        return 'break'

    def draw(self):
        self.delete('decoration')
        w,h = self.winfo_width(),self.winfo_height()
        disabled = self.control_state == 'disabled'
        border = mix('#DDD4E6',PRIMARY,self.focus_amount if not disabled else 0)
        rounded(self,0,0,w,h,16,border,tags='decoration')
        rounded(self,1.5,1.5,w-3,h-3,15,'#F0EBF3' if disabled else '#F5F0F9',tags='decoration')
        self.create_text(17,15,text=self.label,anchor='w',fill=MUTED if disabled else mix(MUTED,PRIMARY,self.focus_amount),
                         font=('Microsoft YaHei UI',-11),tags='decoration')
        self.coords(self.window,17,39)
        self.itemconfigure(self.window,width=max(10,w-(52 if self.dropdown else 34)))
        if self.dropdown:
            self.create_text(w-24,36,text='⌄',fill=MUTED,font=('Segoe UI',-19),tags='decoration')
        self.tag_lower('decoration')


class StatusOrb(AnimatedCanvas):
    def __init__(self, master, variable, active):
        super().__init__(master,bg=master.cget('bg'),width=44,height=44)
        self.variable,self.active = variable,active
        self.tick()

    def tick(self):
        self.delete('all')
        status = self.variable.get()
        running = self.active()
        connected = status == '已连接'
        color = '#25865C' if connected else '#B3261E' if '失败' in status or '不可用' in status else PRIMARY if running else '#A69CB4'
        phase = time.monotonic()*3/MOTION_DURATION_SCALE if MOTION and running else 0
        radius = 14+2*math.sin(phase)
        self.create_oval(22-radius,22-radius,22+radius,22+radius,fill=mix(self.cget('bg'),color,.1),outline='')
        self.create_oval(17,17,27,27,fill=color,outline='')
        if running and not connected:
            self.create_arc(8,8,36,36,start=(phase*70)%360,extent=95,style='arc',outline=color,width=2)
        self.later('pulse',33 if running and MOTION else 250,self.tick)


class Scrollbar(AnimatedCanvas):
    def __init__(self, master, command, bg=BG):
        super().__init__(master,bg=bg,width=9,height=1,cursor='arrow')
        self.command = command
        self.first,self.last,self.offset = 0.,1.,0.
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Button-1>',self.press)
        self.bind('<B1-Motion>',self.drag)

    def set(self, first, last):
        self.first,self.last = float(first),float(last)
        self.draw()

    def thumb(self):
        h = max(1,self.winfo_height())
        size = min(h,max(28,(self.last-self.first)*h))
        travel = h-size
        top = self.first/max(.0001,1-(self.last-self.first))*travel
        return top,size,travel

    def draw(self):
        self.delete('all')
        if self.last-self.first < .999:
            top,size,_ = self.thumb()
            rounded(self,2,top,5,size,2.5,'#CBBED9')

    def press(self, event):
        top,size,_ = self.thumb()
        self.offset = event.y-top if top <= event.y <= top+size else size/2
        self.drag(event)

    def drag(self, event):
        _,_,travel = self.thumb()
        if travel:
            fraction = max(0,min(1,(event.y-self.offset)/travel))*(1-self.last+self.first)
            self.command('moveto',fraction)


def build_material_ui(app):
    root = app.root
    root.title('一键内网穿透GUI工具')
    root.configure(bg=BG)
    root.minsize(700, 620)
    width = min(940, root.winfo_screenwidth()-70)
    height = min(940, root.winfo_screenheight()-100)
    root.geometry(f'{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(0,(root.winfo_screenheight()-height)//2)}')

    # Honor the Windows animation accessibility preference.
    global MOTION
    try:
        import ctypes
        enabled = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(enabled),0):
            MOTION = bool(enabled.value)
    except (AttributeError, OSError):
        pass

    viewport = tk.Canvas(root,bg=BG,highlightthickness=0,bd=0)
    scrollbar = Scrollbar(root,command=viewport.yview)
    viewport.configure(yscrollcommand=scrollbar.set)
    viewport.pack(side='left',fill='both',expand=True)
    outer = tk.Frame(viewport,bg=BG)
    window = viewport.create_window(0,0,window=outer,anchor='nw')
    app.ui_viewport = viewport

    def layout(event=None):
        available = viewport.winfo_width()
        content_width = min(1000,available)
        viewport.itemconfigure(window,width=content_width)
        viewport.coords(window,max(0,(available-content_width)//2),0)
        total = outer.winfo_reqheight()
        viewport.configure(scrollregion=(0,0,available,total))
        if total > viewport.winfo_height()+2:
            if not scrollbar.winfo_manager():
                scrollbar.pack(side='right',fill='y')
        elif scrollbar.winfo_manager():
            scrollbar.pack_forget()
    viewport.bind('<Configure>',layout)
    outer.bind('<Configure>',layout)

    def wheel(event):
        if event.widget is not app.log_widget and outer.winfo_reqheight() > viewport.winfo_height():
            viewport.yview_scroll(-int(event.delta/120),'units')
    root.bind('<MouseWheel>',wheel,add='+')

    content = tk.Frame(outer,bg=BG)
    content.pack(fill='both',expand=True,padx=28,pady=(22,18))
    header = tk.Frame(content,bg=BG)
    header.pack(fill='x',pady=(0,16))
    mark = tk.Canvas(header,width=52,height=52,bg=BG,bd=0,highlightthickness=0)
    mark.pack(side='left',padx=(0,16))
    rounded(mark,0,0,52,52,18,TONAL)
    mark.create_line(15,28,25,18,34,27,fill=PRIMARY,width=2.5,capstyle='round',joinstyle='round')
    mark.create_line(25,18,25,37,fill=PRIMARY,width=2.5,capstyle='round')
    title = tk.Frame(header,bg=BG)
    title.pack(side='left',fill='x',expand=True)
    tk.Label(title,text='一键内网穿透',bg=BG,fg=TEXT,font=('Microsoft YaHei UI',-26,'bold'),anchor='w').pack(fill='x')
    tk.Label(title,text='嗨，想把你的小小世界分享出去吗？交给我吧♪',bg=BG,fg=MUTED,font=FONT,anchor='w').pack(fill='x',pady=(4,0))

    card = Surface(content,padding=20)
    card.pack(fill='x')
    body = card.body
    tk.Label(body,text='连接设置 · 一起准备吧',bg=SURFACE,fg=TEXT,font=('Microsoft YaHei UI',-17,'bold')).pack(anchor='w',pady=(0,10))
    choices = tk.Frame(body,bg=SURFACE)
    choices.pack(fill='x')
    choices.columnconfigure(0,weight=3,uniform='choices')
    choices.columnconfigure(1,weight=2,uniform='choices')
    tk.Label(choices,text='穿透引擎',bg=SURFACE,fg=MUTED,font=('Microsoft YaHei UI',-12)).grid(row=0,column=0,sticky='w',pady=(0,7))
    tk.Label(choices,text='本地服务类型',bg=SURFACE,fg=MUTED,font=('Microsoft YaHei UI',-12)).grid(row=0,column=1,sticky='w',padx=(20,0),pady=(0,7))
    mode = Segments(choices,app.mode,('自动','Cloudflare','FRP'),width=300)
    mode.grid(row=1,column=0,sticky='ew')
    protocol = Segments(choices,app.protocol,('HTTP','HTTPS','TCP'),width=210)
    protocol.grid(row=1,column=1,sticky='ew',padx=(20,0))
    app.editables.extend([(mode,'readonly'),(protocol,'readonly')])
    app.mode_control,app.protocol_control = mode,protocol

    port_row = tk.Frame(body,bg=SURFACE)
    port_row.pack(fill='x',pady=(14,0))
    port_row.columnconfigure(0,weight=1)
    app.port_box = Field(port_row,app.port,'本地端口',dropdown=True)
    app.port_box.grid(row=0,column=0,sticky='ew',padx=(0,12))
    app.editables.append((app.port_box,'normal'))
    app.scan_button = Button(port_row,'帮你找端口',app.scan,width=116)
    app.scan_button.grid(row=0,column=1)
    tk.Label(body,text='告诉我本地端口吧。不记得也没关系，让我帮你找找♪',bg=SURFACE,
             fg=MUTED,font=('Microsoft YaHei UI',-12),anchor='w').pack(fill='x',pady=(6,0))

    actions = tk.Frame(content,bg=BG)
    actions.pack(fill='x',pady=(12,12))
    for index in range(4):
        actions.columnconfigure(index,weight=2 if index==0 else 1)
    app.start_button = Button(actions,'开始穿透  ♪',app.start,variant='filled',width=210,height=54)
    app.stop_button = Button(actions,'停止，歇一会',app.stop,state='disabled',height=54)
    app.restart_button = Button(actions,'重新出发',app.restart,state='disabled',height=54)
    app.background_button = Button(actions,'后台陪着你',root.iconify,variant='text',height=54)
    for i,button in enumerate((app.start_button,app.stop_button,app.restart_button,app.background_button)):
        button.grid(row=0,column=i,sticky='ew',padx=(0,8 if i<3 else 0))

    connection = Surface(content,color='#F0EAF8',padding=16,radius=26)
    connection.pack(fill='x')
    status_body = connection.body
    status_head = tk.Frame(status_body,bg=connection.color)
    status_head.pack(fill='x',pady=(0,6))
    app.status_orb = StatusOrb(status_head,app.status,lambda:app.active)
    app.status_orb.pack(side='left',padx=(0,7))
    status_words = tk.Frame(status_head,bg=connection.color)
    status_words.pack(side='left',fill='x',expand=True)
    tk.Label(status_words,text='连接状态',bg=connection.color,fg=MUTED,font=('Microsoft YaHei UI',-11),anchor='w').pack(fill='x')
    app.status_display = tk.StringVar(value=status_copy(app.status.get()))
    app.status.trace_add('write',lambda *args:app.status_display.set(status_copy(app.status.get())))
    app.status_label = tk.Label(status_words,textvariable=app.status_display,bg=connection.color,fg=TEXT,
                                font=('Microsoft YaHei UI',-16,'bold'),anchor='w')
    app.status_label.pack(fill='x',pady=(2,0))
    addr_row = tk.Frame(status_body,bg=connection.color)
    addr_row.pack(fill='x')
    addr_row.columnconfigure(0,weight=1)
    Field(addr_row,app.address,'公网访问地址',state='readonly').grid(row=0,column=0,sticky='ew')
    Button(addr_row,'复制地址',app.copy_address,width=90,variant='text').grid(row=0,column=1,padx=(8,0))
    Button(addr_row,'去看看 ↗',app.open_address,width=92,variant='text').grid(row=0,column=2)

    app.ui_tab = tk.StringVar(value='运行日志')
    tabs_row = tk.Frame(content,bg=BG)
    tabs_row.pack(fill='x',pady=(14,8))
    tabs = Segments(tabs_row,app.ui_tab,('运行日志','FRP 配置'),width=244)
    tabs.pack(side='left')
    app.tab_control = tabs
    panel = Surface(content,padding=20)
    panel.pack(fill='x')
    log_page = tk.Frame(panel.body,bg=SURFACE)
    settings = tk.Frame(panel.body,bg=SURFACE)
    app.ui_pages = {'运行日志':log_page,'FRP 配置':settings}
    def switch_page(value):
        for page in app.ui_pages.values():
            page.pack_forget()
        app.ui_pages[value].pack(fill='both',expand=True)
        panel.layout()
    tabs.command = switch_page

    log_title = tk.Frame(log_page,bg=SURFACE)
    log_title.pack(fill='x',pady=(0,10))
    tk.Label(log_title,text='我们的连接手记',bg=SURFACE,fg=TEXT,font=('Microsoft YaHei UI',-14,'bold')).pack(side='left')
    tk.Label(log_title,text='每一步，都记着哦',bg=SURFACE,fg=MUTED,font=('Microsoft YaHei UI',-11)).pack(side='right')
    log_body = tk.Frame(log_page,bg=SURFACE)
    log_body.pack(fill='both',expand=True)
    app.log_widget = tk.Text(log_body,height=5,wrap='word',state='disabled',bg=SURFACE,fg=MUTED,
                             relief='flat',bd=0,highlightthickness=0,padx=2,pady=4,
                             font=('Microsoft YaHei UI',-12),spacing1=3,spacing3=3,selectbackground=TONAL)
    log_scroll = Scrollbar(log_body,command=app.log_widget.yview,bg=SURFACE)
    log_scroll.pack(side='right',fill='y')
    app.log_widget.configure(yscrollcommand=log_scroll.set)
    app.log_widget.pack(fill='both',expand=True)
    app.log_widget.configure(state='normal')
    app.log_widget.insert('end','嗨，我在这里哦♪ 点下「开始穿透」，我们就一起出发吧。\n连接进度和运行日志都会留在这里，随时可以回来看看。\n')
    app.log_widget.configure(state='disabled')

    settings.columnconfigure(0,weight=1)
    settings.columnconfigure(1,weight=1)
    fields = [('FRPS 服务器',app.server,0,0,2,False),
              ('服务端口',app.server_port,1,0,1,False),
              ('远程映射端口',app.remote_port,1,1,1,False),
              ('认证 Token',app.token,2,0,1,True),
              ('公网访问主机（可选）',app.public_host,2,1,1,False)]
    for label,variable,row,col,span,secret in fields:
        field = Field(settings,variable,label,show='●' if secret else '')
        field.grid(row=row,column=col,columnspan=span,sticky='ew',pady=(0,10),
                   padx=(0,12) if span==1 and col==0 else 0)
        app.editables.append((field,'normal'))
    hint = tk.Label(settings,text='记得准备好 FRPS 服务端，并放行映射端口哦。Token 只在这次会话里使用。',
                    bg=SURFACE,fg=MUTED,font=('Microsoft YaHei UI',-12),anchor='w',justify='left')
    hint.grid(row=3,column=0,columnspan=2,sticky='ew')
    settings.bind('<Configure>',lambda e:hint.configure(wraplength=max(300,e.width-10)))
    switch_page('运行日志')

    app.footer = tk.Label(content,
        text='让我来选吧：HTTP / HTTPS 用 Cloudflare，TCP 用 FRP。临时地址用于测试哦。\n'
             '后台运行时，我会在任务栏等你；关闭窗口，穿透也会一起停下。',
        bg=BG,fg=MUTED,font=('Microsoft YaHei UI',-11),justify='left',anchor='w')
    app.footer.pack(fill='x',pady=(18,0))
    content.bind('<Configure>',lambda e:app.footer.configure(wraplength=max(320,e.width)))
