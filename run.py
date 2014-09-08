#!/usr/bin/python
import serial
import sys
import os
import time
import curses
from curses.textpad import Textbox, rectangle
import socket
import struct


port = None
current_info = [';']

# Server stuff
TCP_IP = '127.0.0.1'
TCP_PORT = 10001
BUFFER_SIZE = 1024  # Normally 1024, but we want fast response

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((TCP_IP, TCP_PORT))

def open_port():
    if os.uname()[0]=="Darwin":
         default_port_name = '/dev/tty.usbserial'
    else:
         default_port_name = '/dev/ttyUSB0'
    port_name = get_param("Set port to open [leave blank for '"+default_port_name+"']")
    try:
         if port_name == '':
              port_name = default_port_name
         ser = serial.Serial(port_name, 19200, timeout = 0.1) # try a baud rate of 9600, or 4800... also look into the API for the telescope controls
         return ser
    except:
         return None

def current_info_box():
    if current_info == [';']:
        pass
    else:
        new_c_i = []
        for i in range(len(current_info)):
            x = manage_string(current_info[i])
            new_c_i.append(x)
        for i in range(len(current_info)):
            screen.addstr(i + 25, 35, new_c_i[i])

def get_status():
     if port is not None:
          port.readline()
          port.write('!AGas;') # GetAlignmentState
          a = port.readline()
          port.write('!AGai;') # GetAlginmentSide
          b = port.readline()
          port.write('!CGra;') # GetRA
          c = port.readline()
          port.write('!CGde;') # GetDec
          d = port.readline()
          port.write('!CGtr;') # GetTargetRA
          e = port.readline()
          port.write('!CGtd;') # GetTargetDec
          f = port.readline()
          
          #return str(port.readline())
          return [a, b, c, d, e, f]
     else:
          nc = "Not connected."
          return [nc,nc,nc,nc,nc,nc]

def print_obs(name, alignra, aligndec):
    with open(name, 'a') as f:
        port.readline()
        port.write('!CGra;') # GetRA
        curra = port.readline()
        port.write('!CGde;') # GetDec
        curdec = port.readline()
        port.write('!CGtr;') # GetTargetRA
        tarra = port.readline()
        port.write('!CGtd;') # GetTargetDec
        tardec = port.readline()

        f.write(alignra,aligndec,tarra,tardec,curra,curdec)
        

def manage_string(string):
    new_string = ''
    for i in string:
        if i != ';':
            new_string += i
        else:
            break
    
    return new_string

def get_param(prompt):
    win = curses.newwin(5, 60, 5, 5)
    win.border(0)
    win.addstr(1,2,prompt)
    return win.getstr(3,2,55)

def open_server():
    s.listen(1)
    print "Listening on", TCP_IP, TCP_PORT
    conn,addr = s.accept()
    conn.settimeout(1)
    return (conn,addr)

def unpack_command(command):
    """ Unpack the data recieved from stellarium, and converts into coordinates in RA and DEC"""
    print command
    data = struct.unpack('<hhQIi',command)
    RA_raw = data[-2]  # a value of 0x100000000 = 0x0 means 24h=0h,
                       # a value of 0x80000000 means 12h
                       # 12h = 2147483648 
    DEC_raw = data[-1] # a value of -0x40000000 means -90 degrees
                       # a value of 0x0 means 0 degrees
                       #  a value of 0x40000000 means 90 degrees
                       # 90d = 1073741824
    dec = float(DEC_raw)/1073741824.0*90.0
    if dec > 0:
        dec_string = "+" + str(int(dec)) + ":" + str(int(dec%1*60)) + ":" + str(round(dec%1*60%1*60, 1)) # convert from decimal into dms
    else:
        dec_string = str(int(dec)) + ":" + str(int(dec%1*60)) + ":" + str(round(dec%1*60%1*60, 1)) # convert from decimal into dms
    ra = float(RA_raw)/2147483648.0 *12.0
    ra_string = str(int(ra)) + ":" + str(int(ra%1*60)) + ":" + str(round(ra%1*60%1*60, 1)) # convert from decimal into hms
    return (ra_string,dec_string)


help_list = ['o - Open Port', 'e - Set Alignment Side', 
             'r - Target Right Ascension', 'd - Target Declination', 
             'a - Align from Target/(align from next stellarium slew)', 
             'g - GoTo Target', 'u - Update Current Info',
             'v - Void alignment',
             'b - Return to previous target',
             's - Open/close server commands',
             'f - Change output filename',
             'p - Print observation data',
         '------------','q - Exit']

current_info_titles = ['Alignment State:', 'Side of the Sky:',
                       'Current Right Ascension:', 'Current Declination:',
                       'Target Right Ascension:', 'Target Declination:',
                       '']

conn = None
addr = None
server_running = False
stell_align = False
RA = None
DEC = None
alignRA = None
alignDEC = None
tarRA = None
tarDEC = None
filename = "observations.txt"
screen = curses.initscr()
screen.timeout(50) #stops getch() from blocking
start_time = time.time()

good = True
while good: 

    screen.clear()
    screen.border(0)
    screen.addstr(2, 2, "UTSC Python Telescope control system")
    for i in range(len(help_list)):
        screen.addstr(i + 3, 4, help_list[i])
    for i in range(len(current_info_titles)):
        screen.addstr(i + 25, 4, current_info_titles[i])
    current_info_box()
    current_time = time.time()
    if port is not None:
        if current_time - start_time > 2:
            current_info = get_status()
            start_time = current_time # only update the infos every 2 seconds
    screen.refresh()
    key = screen.getch()

##########################
# Server stuff
    if server_running:
        data = None
        try:
            data = conn.recv(BUFFER_SIZE)
        except: # connection timeout, assume no data sent
            data = None
        if data is not None:
            RA, DEC = unpack_command(data) 
            data = None
            #conn.send(data)  TODO: return to stellarium the current RA and DEC from the telescope
            if stell_align and DEC is not None and RA is not None:
                stell_align = False
                print "Aligning"
                port.write('!CStd' + DEC + ';')
                alignDEC = DEC
                print port.readline()
                port.write('!CStr' + RA + ';')
                alignRA = RA
                print port.readline()
                port.write('!AFrn;')
                print port.readline()
                print "Alignment complete"
            elif DEC is not None and RA is not None:
                print "Go to object"
                port.write('!CStd' + DEC + ';')
                print port.readline()
                port.write('!CStr' + RA + ';')
                print port.readline()
                port.write('!GTrd;')
                print port.readline()
                print "goto complete"


##########################    
# Main comamnds

# Exit
    if key == 27 or key == ord('q'): #27=ESC
        good = False

    # Open port
    if key == ord('o'):
        port = open_port()

    # Set target declination
    if key == ord('d'):
        dec = get_param("Set target Declination [+dd:mm:ss]")
        if port is not None:
            port.write('!CStd' + dec + ';')

    # Set target right ascension
    if key == ord('r'):
        ra = get_param("Set target Right Ascension [hh:mm:dd]")
        if port is not None:
             port.write('!CStr' + ra + ';')

    # Set alignment side
    if key == ord('e'):
        direction = get_param("Set alignment side [West/East]")
        if direction == "West" or direction == "East": # Check for valid input
            if port is not None:
                 port.write('!ASas' + direction + ';')

    # Align from target
    if key == ord('a'):
        if port is not None:
            if server_running:
                stell_align = True
            else:
                port.write('!AFrn;')
                alignRA = tarRA
                alignDEC = tarDEC

    # Goto target
    if key == ord('g'):
        if port is not None:
             port.write('!GTrd;')
             print port.readline()
    
    # Void alignment
    if key == ord('v'):
        if port is not None:
             port.write('!AVoi;')

    # previous alignment
    if key == ord('b'):
        if port is not None:
             port.write('!GTol;')
    
    # Open Server
    if key == ord('s'):
        if server_running:
            server_running = False
            print "Closing connection"
            conn.close()
        else:
            conn, addr = open_server()
            server_running = True
            print "Server open"
    
    # Change output filename
    if key == ord('f'):
        if port is not None:
            filename = get_param("Output Filename")

    # Print alignment RA, DEC, Target RA, DEC and Current RA, DEC to filename
    if key == ord('p'):
        if port is not None:
            print_obs(filename, alignRA, alignDEC)
            print "Printed"

    # Update information
    if key == ord('u'):
        current_info = get_status()

curses.endwin()
