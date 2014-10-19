#!/usr/bin/python
import serial
import os
import time
import curses
import socket
import struct
import time

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
            ('o','Open serial port',                telescope.open_port), 
            ('e','Set alignment side',              telescope.set_alignment_side), 
            ('r','Target right ascension',          telescope.set_target_rightascension), 
            ('d','Target declination',              telescope.set_target_declination), 
            ('a','Align from target',               telescope.align_from_target), 
            ('g','Go to target',                    telescope.go_to_target), 
            ('v','Void alignment',                  telescope.void_alignment),
            ('b','Return to previous target',       telescope.previous_alignment),
            ('s','Start Stellarium server',         telescope.start_server),
            ('t','Toggle Stellarium mode',          telescope.toggle_stellarium_mode),
            ('p','Write telescope readout to file', telescope.write_telescope_readout),
            ('c','Execute custom command',          telescope.send_custom_command),
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
        self.window_status = curses.newwin(6,67,ypos,2)                                  
        ypos += self.window_status.getmaxyx()[0]
        self.window_telescope = curses.newwin(3+len(telescope.telescope_states),67,ypos,2)                                  
        self.maxmessages = 6;
        self.messages = []
        self.push_message("PTCS initialized.")
        ypos += self.window_telescope.getmaxyx()[0]
        self.window_messages = curses.newwin(3+self.maxmessages,67,ypos,2)                                  

    def push_message(self,message):
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
        # Port
        self.window_status.addstr(2, 2, "Serial port")                    
        portname = "Not open"
        if telescope.serialport:
            portname = telescope.serialport.name
        self.window_status.addstr(2, 19, portname )                    
        # Server
        self.window_status.addstr(3, 2, "Server")                    
        serverstatus = "Not running"
        if telescope.socket is not None:
            if telescope.conn is not None:
                serverstatus = "Connected" 
            else:
                serverstatus = "Waiting for connection" 
        self.window_status.addstr(3, 19, serverstatus )                    
        self.window_status.addstr(4, 2, "Stellarium mode")                    
        if telescope.stellarium_mode==0:
            stellarium_mode = "Align to next coordinates"
        else:
            stellarium_mode = "Go to next coordinates"
        self.window_status.addstr(4, 19, stellarium_mode )                    
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
            self.window_telescope.addstr(index+2, 4, element[0])                    
            self.window_telescope.addstr(index+2, 32, element[2])                    
        self.window_telescope.refresh()


telescope = None    # Singleton
class Telescope():
    def __init__(self, stdscreen):
        global telescope
        telescope = self
        self.last_telescope_update = 0
        self.conn = None
        self.socket = None
        self.serialport = None
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
                    self.serialport.read(1024) # empty buffer
                    for (index,element) in enumerate(self.telescope_states):
                        self.serialport.write(element[1]) 
                        element[2] = self.serialport.read(1024).strip() 
                        if element[2][0] == chr(0x8F):
                            element[2] = "ATCL_ACK"
                        if element[2][0] == chr(0xA5):
                            element[2] = "ATCL_NACK"
                        if element[2][-1] == ";":
                            element[2] = element[2][:-1]
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
            # Poll socket for Stellarium
            if self.socket is not None:
                if self.conn is None:
                    try:
                        self.conn, addr = self.socket.accept()
                        self.push_message("Connection established from %s:%d."% addr)
                    except socket.error as e:
                        pass
                else:
                    try:
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
        
    def toggle_stellarium_mode(self):
        self.stellarium_mode = not self.stellarium_mode

    def start_server(self):
        if self.socket == None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            port = 10001
            try:
                self.socket.bind(("", port))
                self.socket.listen(1)
                self.socket.setblocking(0)
                self.push_message("Server waiting for connection on port %d."%port)
            except socket.error as e:
                self.push_message("Socket error (%s)"%e.strerror)
                self.socket = None
        else:
            self.push_message("Server already running.")
    
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

    def open_port(self):
        if os.uname()[0]=="Darwin":
            default_port_name = '/dev/tty.usbserial'
        else:
            default_port_name = '/dev/ttyUSB0'
        port_name = self.get_param("Serial port to open [leave blank for '"+default_port_name+"']")
        try:
            if port_name == '':
                port_name = default_port_name
            self.serialport = serial.Serial(port_name, 19200, timeout = 0.1) 
            self.push_message("Successfully opened serial port.")
        except:
            self.push_message("Opening serial port failed.")
            self.serialport = None
    
    def send(self,data):
        if len(data)<1:
            return False
        elif self.serialport is not None:
            self.serialport.write(data)
            self.push_message("Sent '%s' to telescope."%data)
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
        exit()

        
if __name__ == '__main__':                                                       
    curses.wrapper(Telescope)

