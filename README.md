# LANTERN

![lab_logo](https://github.com/user-attachments/assets/6ae06c25-0459-4676-a054-f8e9962b4b88)

Created by the [Hamdoun lab at the Scripps Institution of Oceanography](https://www.hamdounlab.org).

LANTERN (Lytechinus Automated Navigation Tracking and Ethogram Recognition Network) is a computer vision-based system designed to autonomously track the 3D location of a painted sea urchin, L. pictus, within a lab-based tank. This repository contains:

a) A YOLOv12n model trained to recognize roving L. pictus.

b) A series of scripts that apply this model to identify L. pictus in parallel to live footage collection on a Raspberry Pi 5's Camera Module 3 Wide.

c) Instructions on how to use the above scripts so you can perform live inference of your own.

d) 3D printer-ready .3mf files of the lid and custom tank used in our lab. Note that this system can be adapted to any desired camera configuration.

============================================================================

Before beginning, make sure you have obtained the following:

a) Raspberry Pi 5 (x2). You can format each of the Pis using the Raspberry Pi Imager. During formatting, you will want to install the Raspberry Pi OS (Legacy, 64-bit) containing a port of Debian Bookworm. Installing the wrong OS can cause several of the packages used by this code to break.

b) Camera Module 3 Wide (x1). One of the Pis should have an attached Camera Module 3 and one will not. From this point onward, the Pi with the Camera Module 3 unit will be referred to as the remote Pi while the Pi without the Camera Module 3 unit will be referred to as the local Pi. The remote Pi will be used to collect and label assay footage in your experimental area, while the local Pi will send commands and direct LANTERN from an office or non-experimental lab space.

c) Physical mount for your cameras. You can either 3D print the mounts used by our lab by referencing the attached .gcode files or design your own. Note that the .gcode files are set to print using PLA Basic; if you are using a different material, you will want to open the files in a 3D print editor and export again. You will want to make sure that the Camera Module 3 unit is mounted such that it can see the urchin you are tracking and the entire plane that the urchin will be moving around on.

d) Arduino Nano Every (x1), breadboard (x1), and appropriate wiring. You will be wiring the Arduino to the local Pi using the below diagram. If you wish to run multiple LANTERN units or camera, you will follow this same wiring process for every local Pi attached to the Arduino:

<img width="287" height="470" alt="wiringDiagram" src="https://github.com/user-attachments/assets/1fea22ef-ca4f-4273-9419-e5f66fdacf68" />

============================================================================

Once you have obtained the necessary physical components, perform the following software setup steps:

a) On the remote Pi, create a virtual environment using `python3 -m venv –system-site-packages venv` on the command line. 

b) Within your venv, install pip and Ultralytics via `python -m pip install -U pip` and `python -m pip install ultralytics`. 

c) Then, still within your venv, uninstall numpy via `python -m pip uninstall numpy`.

d) Download **urchinCV.pt** and **remoteDaemon.py** from this repository onto the remote Pi, **localTrigger.py** onto your local Pi, and **arduinoPulse.ino** onto the device you will be using to trigger your recording.

You are now ready to begin using LANTERN.

============================================================================

1) Check and record the IP addresses of all of your Pis using `hostname -I` from the command line. You will want to make sure that the network your Pis are connected to will allow you to maintain stable IP addresses. Both the remote and local Pis should be connected to the same network.

2) Physically prepare your system for recording. Your local Pi will be wired to another device (any computer is fine, so long as it can run **Arduino IDE** and **arduinoPulse.ino**). Your remote Pi will be wherever you are recording.

3) Connect to your remote Pi from the local Pi via ssh by running `ssh **PI USERNAME**@**REMOTE PI IP ADDRESS**` from the command line.

4) Open your virtual environment on the remote Pi. Run **remoteDaemon.py** with `remoteDaemon.py --local-ip **IP OF THE LINKED LOCAL PI** --model-path **PATH TO urchinCV.pt** --capture-duration **LENGTH OF DESIRED RECORDING** --output-folder **LOCATION TO SAVE RECORDINGS AND BOUNDING BOXES TO**`. You should see the message: **Expected message: START**.

5) Run **localTrigger.py** with `localTrigger.py --remote-host **IP OF THE LINKED REMOTE PI** --remote-user **USERNAME ON LINKED REMOTE PI** --set-time-out **TIME OUT TIME IN SECONDS, MUST BE LONGER THAN RECORDING TIME`. You should see the message: **Waiting for Arduino pulse...**.

6) Run **arduinoPulse.ino**. This should immediately trigger the message **Pulse at TIME. Sent firing key at TIME.** on your local Pis and the message **Starting recording.** on your remote Pi.

7) Once the designated recording time as passed, you will see the following message on your remote Pi: **Finished recording. Press Ctrl + C to stop the program.** When the recording finishes, a video of the recording (containing bounding boxes) and a .csv file containing the coordinates of the bounding box(es) from each frame will be saved at the location designated in step 4.
