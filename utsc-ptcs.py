#!/usr/bin/python
# UTSC | PTCS 
# University of Toronto Scarborough | Python Telescope Control System
#
# Copyright (c) 2014 Eric Dapp, Caden Armstrong, Hanno Rein
#
# UTSC | PCTS is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# UTSC | PCTS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with UTSC | PCTS.  If not, see <http://www.gnu.org/licenses/>.
#
import serial
#from PIL import ImageTk, Image
import os
import time
import curses
import socket 
import struct
import time
import sys
import subprocess
import signal
#import Tkinter as tk
from PIL import Image, ImageFilter, ImageChops, ImageStat
import numpy as np



## Conversion functions
def dec_str2raw(s):
    f = [float(i) for i in s.split(":")]
    if f[0]<0.:
        dec = f[0]-f[1]/60.-f[2]/60./60. 
    else:
        dec = f[0]+f[1]/60.+f[2]/60./60. 
    return int(dec*1073741824.0/90.0)

def ra_str2raw(s):
    f = [float(i) for i in s.split(":")]
    ra = f[0]+f[1]/60.+f[2]/60./60.
    return int(ra*2147483648.0/12.0)

def dec_raw2str(raw):
    dec = float(raw)/1073741824.0*90.0
    return "%+02d:%02d:%02d" % (int(dec), int(abs(dec)%1*60), round(abs(dec)%1*60%1*60, 1))

def ra_raw2str(raw):
    ra = float(raw)/2147483648.0 *12.0
    return  "%02d:%02d:%02d" % (int(ra),  int(ra%1*60),  round(ra%1*60%1*60, 1)) 


class Menu():                                                          
    def __init__(self):
        self.position = 0                                                    
        self.menuitems = [
            ('o','Open serial port for telescope',  telescope.open_port), 
            ('O','Open serial port for RoboFocus',  telescope.open_robofocus_port), 
            ('e','Set alignment side',              telescope.set_alignment_side), 
            #('a','Align from target',               telescope.align_from_target), 
            # ('v','Void alignment',                  telescope.void_alignment),
            ('s','Start Stellarium server',         telescope.start_server),
            ('t','Toggle Stellarium mode',          telescope.toggle_stellarium_mode),
            # ('p','Write telescope readout to file', telescope.write_telescope_readout),
            #('b','Return to previous target',       telescope.previous_alignment),
            ('g','Go to target',                    telescope.go_to_target), 
            ('m','Move RoboFocus',                  telescope.robofocus_userinput),
            ('F','Start Auto focus',                  telescope.start_autofocus),
            #('R','Target right ascension',          telescope.set_target_rightascension), 
            #('d','Target declination',              telescope.set_target_declination), 
            #('C','Execute custom telescope command',telescope.send_custom_command),
            ('r','Read camera settings',            telescope.read_camera),
            ('I','Set camera ISO',                  telescope.define_iso),
            ('S','Set camera shutter speed',        telescope.shutter_speed),
            ('N','Set camera number of pictures',   telescope.numberofpictures),
            ('c','Capture images',                  telescope.capture_images),
            ('q','Exit',                            telescope.exit)
            ]
        self.window = curses.newwin(len(self.menuitems)+2,67,4,2)                                  
        self.window.keypad(1)                                                
        self.window.timeout(100)    # in ms
        
    def display(self):                                                       
        self.window.border(0)
        for index, item in enumerate(self.menuitems):                        
            if index == self.position:                                   
                mode = curses.A_REVERSE                                  
            else:                                                        
                mode = curses.A_NORMAL                                   
            msg = ' %s - %s ' % (item[0],item[1])                            
            self.window.addstr(1+index, 1, msg, mode)                    

        key = self.window.getch()                                        

        if key in [curses.KEY_ENTER, ord('\n')]:                         
            self.menuitems[self.position][2]()                           
        elif key == curses.KEY_UP:                                       
            self.position -= 1                                                   
            if self.position < 0:                                                
                self.position = 0                                                
        elif key == curses.KEY_DOWN:                                     
            self.position += 1                                                   
            if self.position >= len(self.menuitems):                               
                self.position = len(self.menuitems)-1                                
        else:
            for (index,m) in enumerate(self.menuitems):
                if ord(m[0])==key:
                    self.position=index
                    m[2]()


class Status():                                                          
    def __init__(self):
        ypos = 4+telescope.menu.window.getmaxyx()[0]
        self.window_status = curses.newwin(8,67,ypos,2)                                  
        ypos += self.window_status.getmaxyx()[0]
        self.window_telescope = curses.newwin(3+len(telescope.telescope_states),67,ypos,2)                                  
        self.maxmessages = 16;
        self.messages = []
        self.push_message("PTCS initialized.")
        ypos += self.window_telescope.getmaxyx()[0]
        self.window_messages = curses.newwin(3+self.maxmessages,67,ypos,2)                                  

    def push_message(self,message):
        if isinstance(message, str):
            message = message.strip()
            if len(message)>0:
                timestamp = time.strftime("%H:%M:%S", time.gmtime())                    
                self.messages.insert(0,"%s %s" %(timestamp,message))
                if len(self.messages)>self.maxmessages:
                    self.messages.pop()
        
    def display(self):                                                       
        self.window_status.clear()
        self.window_status.border(0)
        # Time
        self.window_status.addstr(1, 2, "Time (UTC)")                    
        self.window_status.addstr(1, 19, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))                    
        # Port Telescope
        self.window_status.addstr(2, 2, "Telescope port")                    
        portname = "Not open"
        if telescope.serialport:
            portname = telescope.serialport.name
        self.window_status.addstr(2, 19, portname )                    
        # Port Robofocus
        self.window_status.addstr(3, 2, "RoboFocus port")                    
        portname = "Not open"
        if telescope.robofocus_serialport:
            portname = telescope.robofocus_serialport.name
        self.window_status.addstr(3, 19, portname )                    
        # Server
        self.window_status.addstr(4, 2, "Server")                    
        serverstatus = "Not running"
        if telescope.socket is not None:
            if telescope.conn is not None:
                serverstatus = "Connected" 
            else:
                serverstatus = "Waiting for connection" 
        self.window_status.addstr(4, 19, serverstatus )                    
        self.window_status.addstr(5, 2, "Stellarium mode")                    
        if telescope.stellarium_mode==0:
            stellarium_mode = "Align to next coordinates"
        else:
            stellarium_mode = "Go to next coordinates"
        self.window_status.addstr(5, 19, stellarium_mode )                    
        
        self.window_status.addstr(6, 2, "Camera")                    
        self.window_status.addstr(6, 19, telescope.camera)                    
        self.window_status.refresh()
        
        # Status Messages
        self.window_messages.clear()
        self.window_messages.border(0)
        self.window_messages.addstr(1, 2, "Status messages", curses.A_BOLD)                    
        for (index,message) in enumerate(self.messages):
            self.window_messages.addstr(2+index, 4, message)                    
        self.window_messages.refresh()
        
        # Telescope readout
        self.window_telescope.clear()
        self.window_telescope.border(0)
        self.window_telescope.addstr(1, 2, "Telescope readout", curses.A_BOLD)                    
        for (index,element) in enumerate(telescope.telescope_states):
            self.window_telescope.addstr(index+2, 2, element[0])                    
            self.window_telescope.addstr(index+2, 28, element[2])                    
        self.window_telescope.addstr(1, 48, "RoboFocus readout", curses.A_BOLD)                    
        for (index,element) in enumerate(telescope.robofocus_states):
            self.window_telescope.addstr(index+2, 2+46, element[0])                    
            self.window_telescope.addstr(index+2, 2+46+10, element[2])                    
        
        self.window_telescope.addstr(4, 48, "Camera settings", curses.A_BOLD)                    
        self.window_telescope.addstr(5, 48, "ISO       %s"% telescope.camera_iso)                    
        if "bulb" not in telescope.camera_shutter:
            if "N/A" not in telescope.camera_shutter and "bulb":
                self.window_telescope.addstr(6, 48, "Shutter   %ss"% telescope.camera_shutter)                    
            else:
                self.window_telescope.addstr(6, 48, "Shutter   %s"% telescope.camera_shutter)                    
        else:
            self.window_telescope.addstr(6, 48, "Shutter   %ds (b)"% telescope.camera_longexpshutter)                    
        self.window_telescope.addstr(7, 48, "Num       %d/%d"% (telescope.camera_numtaken,telescope.camera_num))                   
        self.window_telescope.refresh()

telescope = None    # Singleton
class Telescope():
    def __init__(self, stdscreen):
        global telescope
        telescope = self
        self.camera         = "Never read"
        self.camera_iso     = "N/A"
        self.camera_shutter = "N/A"
        self.camera_longexpshutter = 5
        self.camera_num = 1
        self.camera_status = 0
        self.camera_numtaken = 0
        self.camera_path = None
        self.last_telescope_update = 0
        self.last_robofocus_update = 0
        self.autofocusmode = "off" # States are "off", "coarse", "fine"
        self.autofocuslevels= []
        self.autofocuspoints= []
        self.conn = None
        self.socket = None
        self.serialport = None
        self.robofocus_serialport = None
        self.logfilename = "observations.log"
        self.stellarium_mode = 0  # align
        self.screen = stdscreen                                              
        curses.curs_set(0)
        self.screen.addstr(1, 2, "UTSC | PTCS", curses.A_BOLD)
        self.screen.addstr(2, 2, "University of Toronto Scarborough | Python Telescope Control System", curses.A_BOLD)
        self.telescope_states= [
            ['Alignment state',              '!AGas;', ""],  
            ['Side of the sky',              '!AGai;', ""],
            ['Current right ascension',      '!CGra;', ""],
            ['Current declination',          '!CGde;', ""],
            ['Target right ascension',       '!CGtr;', ""],
            ['Target declination',           '!CGtd;', ""]
        ]
        self.robofocus_states= [
            ['Version',         'FV', ""],  
            ['Position',        'FD', ""]
        ]
        self.screen.refresh()
        self.screen.immedok(True)
        self.menu = Menu()                       
        self.status = Status()    
        ## Main loop
        while True:
            # Get telescope heartbeat
            if time.time() - self.last_telescope_update > 2.: # only update the infos every 2 seconds
                self.last_telescope_update = time.time()
                if self.serialport is not None:
                    try:
                        self.serialport.read(1024) # empty buffer
                        for (index,element) in enumerate(self.telescope_states):
                            self.serialport.write(element[1]) 
                            time.sleep(0.05)
                            ret = self.serialport.read(1024).strip() 
                            atcl_asynch = ret.split(chr(0x9F))
                            if len(atcl_asynch)>1:
                                ret = atcl_asynch[0]
                            if len(ret)>0:
                                if ret[0] == chr(0x8F):
                                    ret = "ATCL_ACK"
                                if ret[0] == chr(0xA5):
                                    ret = "ATCL_NACK"
                                if ret[-1] == ";":
                                    ret = ret[:-1]
                            else:
                                ret = "N/A"
                            element[2] = ret
                    except:
                        if self.serialport is not None:
                            if self.serialport.isOpen():
                                self.serialport.close()
                        self.push_message("Something is wrong. Closing serial connection to telescope.")
                else:
                    for (index,element) in enumerate(self.telescope_states):
                        element[2] = "N/A"
                # Send data to stellarium
                if self.socket is not None:
                    if self.conn is not None:
                        try:
                            for (desc, command, value) in self.telescope_states:
                                if command == '!CGra;':
                                    ra = ra_str2raw(value)
                                if command == '!CGde;':
                                    dec = dec_str2raw(value)
                            data = struct.pack('<hhQIii',24,0,int(round(time.time() * 1000)), ra, dec, 0)
                            telescope.conn.send(data)
                        except:
                            pass
            # Get RoboFocus heartbeat
            if time.time() - self.last_robofocus_update > 1.: # only update the infos every second
                self.last_robofocus_update = time.time()
                if self.robofocus_serialport is not None:
                    self.robofocus_parse()
                else:
                    for (index,element) in enumerate(self.robofocus_states):
                        element[2] = "N/A"
            # Poll socket for Stellarium
            if self.socket is not None:
                if self.conn is None:
                    try:
                        self.conn, addr = self.socket.accept()
                        self.conn.settimeout(0)
                        #socket.setblocking(0)
                        self.push_message("Connection established from %s:%d."% addr)
                    except socket.error as e:
                        pass
                else:
                    try:
                        time.sleep(0.01)
                        data = self.conn.recv(1024)
                        if len(data)==20:   # goto command
                            data = struct.unpack('<hhQIi',data)
                            ra_string, dec_string = ra_raw2str(data[-2]), dec_raw2str(data[-1])
                            self.push_message("Received from stellarium: %s %s" % (ra_string,dec_string))
                            self.send('!CStr' + ra_string + ';')
                            self.send('!CStd' + dec_string + ';')
                            if self.stellarium_mode==0:
                                self.align_from_target()
                            else: 
                                self.go_to_target()
                        elif len(data)==0:
                            pass
                        else:
                            self.push_message("Unknown command received of length %d."%len(data))
                    except socket.error as e:
                        pass
            # Refresh display
            self.menu.display()
            self.status.display()
            self.camera_check()
            self.check_autofocus()
    
    def push_message(self, message):
        self.status.push_message(message)

    def get_param(self, prompt):
        win = curses.newwin(5, 62, 5, 5)
        curses.echo()
        curses.curs_set(2)
        win.border(0)
        win.addstr(1,2,prompt)
        r = win.getstr(3,2,55)
        curses.noecho()
        curses.curs_set(0)
        self.screen.refresh()
        return r

    #################### Stellarium communication functions ######################
    def toggle_stellarium_mode(self):
        self.stellarium_mode = not self.stellarium_mode

    def start_server(self):
        if self.socket == None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            port = 10001
            try:
                self.socket.settimeout(0)
                self.socket.bind(("127.0.0.1", port))
                self.socket.listen(1)
                self.push_message("Server waiting for connection on port %d."%port)
            except socket.error as e:
                self.push_message("Socket error (%s)"%e.strerror)
                self.socket = None
        else:
            self.push_message("Server already running.")
    
    #################### Telescope communication functions ######################
    def open_port(self):
        if os.uname()[0]=="Darwin":
            default_port_name = '/dev/tty.usbserial'
        else:
            default_port_name = '/dev/ttyS0'
        port_name = self.get_param("Telescope serial port [leave blank for '"+default_port_name+"']")
        try:
            if port_name == '':
                port_name = default_port_name
            self.serialport = serial.Serial(port_name, 19200, timeout = 0.01) 
            self.push_message("Successfully opened serial port for telescope.")
        except:
            self.serialport = None
            self.push_message("Opening serial port for telescope failed.")
    
    def send(self,data):
        if len(data)<1:
            return False
        elif self.serialport is not None:
            self.serialport.read(10240)
            self.serialport.write(data)
            self.push_message("Sent '%s' to telescope."%data)
            time.sleep(0.5)
            ret = self.serialport.read(1024)
            for r in ret.split(";"): 
                self.push_message("Received: %s."%r)

            return True
        else:
            self.push_message("Did NOT send data to telescope (port not open).")
            return False
    
    def set_alignment_side(self):
        direction = self.get_param("Set alignment side [West/East]")
        if direction == "West" or direction == "East": 
            self.send('!ASas' + direction + ';')
        else:
            self.push_message("Not a valid alignment side.")

    def set_target_rightascension(self):
        ra = self.get_param("Set target Right Ascension [hh:mm:dd]")
        if len(ra)>0:
            self.send('!CStr' + ra + ';')
        else:
            self.push_message("Did not receive user input.")

#******DAN, ARI, KIM, NEW CAMERA DEF************************************
    def read_camera(self):
        # Kill procs
        if sys.platform == "darwin":
            print("Killing PTPCamera process")
            os.system("killall PTPCamera")
            os.system("killall Type4Camera")
        # Get Name
        os.system("gphoto2 --auto-detect > .gphoto.tmp")
        with open(".gphoto.tmp") as f:
            lines = f.readlines()
            if len(lines)>2:
                line = lines[2]
                if "usb:" in line:
                    telescope.camera = line.split("usb:")[0].strip()
                    # Get ISO Setting
                    os.system("gphoto2 --get-config=iso > .gphoto.tmp" )
                    with open(".gphoto.tmp") as f:
                        lines = f.readlines()
                        for line in lines:
                            if "Current:" in line:
                                telescope.camera_iso = line.split("Current:")[1].strip()
                    # Get Shutter speed
                    os.system("gphoto2 --get-config=shutterspeed > .gphoto.tmp" )
                    with open(".gphoto.tmp") as f:
                        lines = f.readlines()
                        for line in lines:
                            if "Current:" in line:
                                telescope.camera_shutter = line.split("Current:")[1].strip()
            else:
                self.push_message("No camera found.")

    def define_iso(self):
        iso_value = self.get_param("Set ISO value 100, 200, 400, 800, 1600, 3200, 6400:")
        if len(iso_value)>0:
            os.system("gphoto2 --set-config capture=on --set-config iso=" + iso_value )
        self.read_camera()

    def shutter_speed(self):
        shutter_value = self.get_param("Enter exposure time in s, e.g. 1, 5, 20, 1/10:")
        if len(shutter_value)>0:
            try:
                svi = int(shutter_value)
            except:
                svi = 1
            if svi<30:
                os.system("gphoto2 --set-config capture=on --set-config shutterspeed=" + shutter_value )
            else:
                os.system("gphoto2 --set-config shutterspeed=bulb")
                telescope.camera_longexpshutter = int(shutter_value)
        self.read_camera()

    def numberofpictures(self):
        num_value = self.get_param("Number of pictures [default 1]")
        if len(num_value)>0:
            telescope.camera_num = int(num_value)
        else:
            telescope.camera_num = 1

#def rename(name, num):
#renamecmd = "mv %s %s%i.jpg"%("capt0000.jpg",name,num)
#os.system(renamecmd)

    def capture_images(self):
        filename = self.get_param("Filename [default: test]")
        self.read_camera()
        if len(filename)<1:
            filename = "test"
        folder = 'pictures/'
        if not os.path.exists(folder):
            self.push_message("Creating folder '"+folder+"'.")
            os.system("mkdir "+folder)
        telescope.camera_path = ''+folder+''+filename
        telescope.camera_numtaken = 0
        telescope.camera_status = 1
    # ==========================
    # Method to automate Focusing 
    # experimental 
    # ==========================
    def capture_focus_image(self):
        filename = "focus"
        self.read_camera()
        folder = 'pictures/'
        if not os.path.exists(folder):
            self.push_message("Creating folder '"+folder+"'.")
            os.system("mkdir "+folder)
        telescope.camera_path = ''+folder+''+filename
        telescope.camera_numtaken = 0
        telescope.camera_status = 1
    # ==========================

    def camera_check(self):
        if telescope.camera_status == 0:
            return
        if telescope.camera_numtaken >= telescope.camera_num:
            if os.path.isfile(".gphoto.tmp"):
                self.push_message("All pictures taken.")
                telescope.camera_status = 0
            return
             
        if telescope.camera_status==1 or os.path.isfile(".gphoto.tmp"):
            os.system("rm -f .gphoto.tmp")
            if "bulb" not in telescope.camera_shutter:
                self.push_message("Taking picture %d of %d." %(telescope.camera_numtaken+1,telescope.camera_num))
                os.system("(gphoto2 --capture-image-and-download --force-overwrite --filename=%s_%04d.jpg >/dev/null; echo 1 > .gphoto.tmp) &"%(telescope.camera_path,telescope.camera_numtaken))
            else:
                self.push_message("Taking picture %d of %d (%ds long exp)." %(telescope.camera_numtaken+1,telescope.camera_num,telescope.camera_longexpshutter))
                # gphoto2 --wait-event=2s --set-config eosremoterelease=Immediate --wait-event=5s --set-config eosremoterelease=Off --wait-event-and-download=5s
                os.system("(gphoto2 --wait-event=2s --set-config eosremoterelease=Immediate --wait-event=%ds --set-config eosremoterelease=Off --force-overwrite --filename=%s_%04d.jpg --wait-event-and-download=5s >/dev/null; echo 1 > .gphoto.tmp) &"% (telescope.camera_longexpshutter, telescope.camera_path,telescope.camera_numtaken))
            telescope.camera_status = 2
            telescope.camera_numtaken += 1
            

        # Bulb mode not implemented yet:
        #    cmd = "gphoto2 --set-config shutterspeed=bulb"
        #    cmd = "gphoto2 --set-config bulb=1 eosremoterelease=Immediate --wait-event=120s --set-config eosremoterelease=Off --wait-event-and-download=2s"
        #

        # Live previewing not implemented yet:
        #root = tk.Tk()
        #root.geometry('400x400')
        #canvas = tk.Canvas(root,width=400,height=400)
        #canvas.pack()
        #pilImage = Image.open(telescope.camera_path+"_"+str(a)+".jpg").resize((400, 400),Image.ANTIALIAS)
        #image = ImageTk.PhotoImage(pilImage)
        #imagesprite = canvas.create_image(0,0,image=image,anchor=tk.NW)
        #root.after(1000, lambda: root.destroy()) # Destroy the widget after 30 seconds
        #root.mainloop()


#******NEW CAMERA DEF************************************

    def set_target_declination(self):
        dec = self.get_param("Set target Declination [+dd:mm:ss]")
        if len(dec)>0:
            self.send('!CStd' + dec + ';')
        else:
            self.push_message("Did not receive user input.")

    def align_from_target(self):
        self.send('!AFrn;')

    def go_to_target(self):
        self.send('!GTrd;')
    
    def void_alignment(self):
        self.send('!AVoi;')

    def previous_alignment(self):
        self.send('!GTol;')
    
    def send_custom_command(self):
        command = self.get_param("Command (ommit ! and ;):")
        if len(command)>0:
            command = "!" + command + ";"
            self.send(command)
        else:
            self.push_message("Did not receive user input.")

    def write_telescope_readout(self):
        with open(self.logfilename, 'a') as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S\t", time.gmtime()))                  
            for (desc, command, value) in self.telescope_states:
                f.write(value+"\t")
            f.write(value+"\n")
            self.push_message("Telescope readout saved.")
            f.close()

    #################### Robofocus communication functions ######################
    def open_robofocus_port(self):
        if os.uname()[0]=="Darwin":
            default_port_name = '/dev/tty.usbserial'
        else:
            default_port_name = '/dev/ttyUSB0'
        port_name = self.get_param("RoboFocus serial port [leave blank for '"+default_port_name+"']")
        try:
            if port_name == '':
                port_name = default_port_name
            self.robofocus_serialport = serial.Serial(port_name, 9600, timeout = 0.01) 
            self.push_message("Successfully opened serial port for RoboFocus.")
            self.robofocus_get_version()
        except:
            self.robofocus_serialport = None
            self.push_message("Opening serial port for RoboFocus failed.")
            
    def robofocus_send(self,c):            
        Z = 0
        for i in c:
            Z += ord(i)
        Z = Z%256   # checksum
        self.push_message("Sent '%s' to RoboFocus."%c)
        self.robofocus_serialport.write(c+chr(Z)) 

    def robofocus_read(self):
        r = self.robofocus_decode_readout(self.robofocus_serialport.read(1024))
        self.push_message("Read '%s' from RoboFocus."%r)
        return r

    def robofocus_parse(self):
        self.robofocus_decode_readout(self.robofocus_serialport.read(1024))
        
    def robofocus_decode_readout(self,r):
        if len(r)>0:
            if r[0]=="I" or r[0]=="O": # ignore in/out characters
                return self.robofocus_decode_readout(r[1:])
        ret = ""
        if len(r)>=9:
            Z = 0
            for i in r[:8]:
                Z += ord(i)
            Z = Z%256  # checksum
            if Z==ord(r[8]):
                ret = r[:8]
            else:
                print "Checksum did not match."
            for (index,element) in enumerate(self.robofocus_states):
                if ret[0:2] == element[1]:
                    value = ret[2:]
                    while value[0]=="0":
                        value = value[1:]
                    element[2] = value

        if len(r)>9:
            ret += self.robofocus_decode_readout(r[9:])
        return ret

    def robofocus_get_version(self):
        self.robofocus_serialport.read(1024) # empty buffer
        self.robofocus_send("FV000000") 
        time.sleep(0.15)
        return self.robofocus_read()

    def robofocus_move_in(self,steps):
        self.robofocus_serialport.read(1024) # empty buffer
        self.robofocus_send("FI%06d"%(steps))
        return 

    def robofocus_move_out(self,steps):
        self.robofocus_serialport.read(1024) # empty buffer
        self.robofocus_send("FO%06d"%(steps))
        return 

    def robofocus_userinput(self):
        steps = self.get_param("Move RoboFocus [+=out,-=in]")
        try: 
            steps = int(steps)
        except:
            steps = 0
        self.robofocus_move(steps)

    def robofocus_move(self,steps):
        if steps>=0:
            return self.robofocus_move_out(steps)
        if steps<0:
            return self.robofocus_move_in(-steps)

    # ==========================================
    # AUTO FOCUS FUNCTION 
    # Experimental
    # ==========================================
    def focus_level(filename, s=5):
        try:
            im = Image.open(filename, 'r') # open image
        except:
            print "Failed to open image"
            return None
        imf = im.filter(ImageFIlter.MedianFilter(s))
        d = ImageCHops.subtract(im,imf,1,100)
        fl = ImageStat.Stat(d).stddev[0]
        self.push_message("Focus level: %f"%fl)
        return fl

    def start_autofocus(self):
        params = self.get_param("Auto focus: maxrange(default 500),numsteps(default 10)") # should be like 30,30
        if len(params) < 1:
            params = "500,10"
        try:
            maxrange, numsteps = params.split(",")
            maxrange = int(maxrange)
            numsteps = int(numsteps)
        except:
            self.push_message("Error reading auto focus settings")
            return
        self.autofocusmode = "coarse"
        self.capture_focus_image()
        self.autofocuslevels = []
        self.autofocuspoints = [] 
        stepsize = int(maxrange/numsteps)
        for a in range(0,numsteps):
            self.autofocuspoints.append(a*stepsize)
        return

    def check_autofocus(self):
        if self.autofocusmode == "off":
            return
        self.autofocuslevels.append(self.focus_level("focus_0000.jpg"))
        if len(self.autofocuslevels) == len(self.autofocuspoints): # Done auto focus for this level
            if self.autofocusmode == "coarse":
                self.autofocusmode = "fine"
                minindex = self.autofocuslevels.index(max(self.autofocuslevels))-1
                if minindex > len(self.autofocuslevels)-2:
                    minindex = len(self.autofocuslevels)-3
                if minindex < 0:
                    minindex = 0
                numpoints = len(self.autofocuspoints)
                maxrange = self.autofocuslevels[minindex+2]-self.autofocuslevels[minindex]
                self.autofocuspoints = [] 
                stepsize = int(maxrange/numsteps)
                for a in range(0,numsteps):
                    self.autofocuspoints.append(a*stepsize)
                self.autofocuslevels = []
                self.robofocus_move_out(self.autofocuslevels[-1]-self.autofocuslevels[minindex])
                self.push_message("Finished coarse focus")
                self.capture_focus_image()
                return
                
            elif self.autofocusmode == "fine":
                minindex = self.autofocuslevels.index(max(self.autofocuslevels))
                self.robofocus_move_out(self.autofocuslevels[-1]-self.autofocuslevels[minindex])
                self.autofocuslevels = []
                self.autofocuspoints = [] 
                self.autofocusmode = "off"
                self.push_message("Finished auto focus")
                return
        else:
                self.capture_focus_image()
                move_amount = len(self.autofocuslevels)
                move_amount = self.autofocuspoints[move_amount]-self.autofocuspoints[move_amount-1]
                self.robofocus_move_in(move_amount)
                self.push_message("Auto focus point %i/%i %s"%(len(self.autofocuslevels),len(self.autofocuspoints),self.autofocusmode))
                return


        
    #################### Cleanup functions ######################
    def exit(self):
        if self.socket is not None:
            if self.conn is not None:
                self.conn.close()
                try:
                    sddocket.shutdown(socket.SHUT_RD)
                except:
                    pass
            self.socket.close()
        if self.serialport is not None:
            if self.serialport.isOpen():
                self.serialport.close()
        if self.robofocus_serialport is not None:
            if self.robofocus_serialport.isOpen():
                self.robofocus_serialport.close()
        exit()

        
if __name__ == '__main__':                                                       
    curses.wrapper(Telescope)
