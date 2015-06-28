# UTSC | PTCS
**University of Toronto Scarborough | Python Telescope Control System**

### Purpose
This python script can communicate with the UTSC Telescope via a RS232 connection (via a USB adapter). The telescope uses a SkyWalker controller built by Astrometric Instruments.

### Simple instructions
Simply run `utsc-ptcs.py`. Then open the serial port by pressing `o`. 

### Stellarium settings:
UTSC | PTCS can communicate with Stellarium via the *Stellarium Protocol*.
Start the stellarium server by pressing `s`. 
Use the following setting in Stellarium:
  - External software or a remote controller
  - Coordinate system: Equinox of the Day (JNow)
  - Host: localhost
  - Port: 10001

### Authors
- Eric Dapp
- Caden Armstrong
- Hanno Rein
- Kim Pham
- Ari Silburt
- Dan Dobre 

### License
UTSC | PCTS is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

UTSC | PCTS is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with UTSC | PCTS.  If not, see <http://www.gnu.org/licenses/>.

