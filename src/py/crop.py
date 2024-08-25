#!/usr/bin/env python3
"""
Graphical User Interface (GUI) for cropping Videos to multiple Region Of Interests (ROIs)
"""


__author__ = "Konrad Brambach"
__version__ = "1.0.0"
__license__ = "MIT"


import cv2
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Frame
import os
import ffmpeg
import copy
import subprocess
import pickle
import csv
from PIL import Image, ImageTk


class Roi:
    """
    Class Roi
    A Region Of Interest (ROI) is defined as a rectangle by the top left corner and the bottom right coordinate.
    The ROI has a width and a height.
    """
    def __init__(self):
        # initialization of a new class
        self.coordinates = [
            [0, 0],  # top left corner
            [0, 0]   # bottom right corner
        ]
        self.height = 0     # height of Roi
        self.width = 0      # width of Roi
        self.status = False     # is True, if Roi is new and not yet saved to Roi list

    def reset(self):
        self.coordinates = [[0, 0], [0, 0]]
        self.setStatus(False)

    def setCoordinates(self, i, x, y, sort=True):
        self.coordinates[i] = [x, y]
        if sort:
            self.sortCoordinates()
        self.calculateDimensions()

    def setRoi(self, a, b):
        self.coordinates = [a, b]
        self.sortCoordinates()
        self.calculateDimensions()

    def getHeight(self):
        return self.height

    def getWidth(self):
        return self.width

    def getCoordinates(self, i):
        return self.coordinates[i]

    def sortCoordinates(self):
        self.coordinates = [
            [min(self.coordinates[0][0], self.coordinates[1][0]), min(self.coordinates[0][1], self.coordinates[1][1])],
            [max(self.coordinates[0][0], self.coordinates[1][0]), max(self.coordinates[0][1], self.coordinates[1][1])]
        ]

    def calculateDimensions(self):
        self.width = self.getCoordinates(1)[0] - self.getCoordinates(0)[0]
        self.height = self.getCoordinates(1)[1] - self.getCoordinates(0)[1]

    def setStatus(self, status):
        self.status = status

    def getStatus(self):
        return self.status


class VideoCropperGUI:
    def __init__(self, master, params=None):
        if params:
            self.ffmpeg_executable = params["ffmpeg_executable"]
        self.master = master
        self.master.title("Crop videos")  # title

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            self.master.iconbitmap(icon_path)

        # ==================== VARIABLES ============================
        # Video-related variables
        self.working_video_path = ""
        self.working_roi_list = []
        self.roi = []
        self.roi_dict = {}                  # Create a dictionary to store ROIs for each video

        # Output-related variables
        self.output_folder = ""

        self.initGUI()
        self.roiWindow = None

        self.check_ffmpeg()

        self.videoListByPath = {}

        self.progress_window = None
        self.status_bar = None

    def initGUI(self):
        # ==================== GUI =================================
        # Settings
        btnWidth = 60       # button width

        # Create left and right frames
        frameLeft = Frame(self.master, width=200, height=400)
        frameLeft.grid(row=0, column=0, padx=10, pady=5)

        frameRight = Frame(self.master, width=650, height=400)
        frameRight.grid(row=0, column=1, padx=10, pady=5)

        # -------------------- LEFT FRAME --------------------
        self.btnSelectVideo = tk.Button(frameLeft, text="Add Video", command=self.select_video, width=btnWidth)
        self.btnSelectVideo.grid(row=0, pady=10, columnspan=2)

        self.tree = ttk.Treeview(frameLeft, columns=('Path', 'ROIs', 'Status'), show='headings', selectmode='browse')
        self.tree.heading('Path', text='File Path')
        self.tree.heading('ROIs', text='ROIs')
        self.tree.heading('Status', text='Status')
        self.tree.column('Path', width=400)
        self.tree.column('ROIs', width=50)
        self.tree.column('Status', width=75)
        self.tree.grid(row=1, pady=10, columnspan=2)

        # Button
        self.btnDrawRoi = tk.Button(frameLeft, text="Draw ROI for selected Video", command=self.drawRoi,
                                         width=int(btnWidth / 2))
        self.btnDrawRoi.grid(row=2, column=0, pady=10)

        # Button
        self.btnImportRoi = tk.Button(frameLeft, text="Import ROI for selected Video", command=self.import_roi,
                                           width=int(btnWidth / 2))
        self.btnImportRoi.grid(row=2, column=1, pady=10)

        # Button
        self.btnRemoveVid = tk.Button(frameLeft, text="Remove selected video", command=self.remove_selected_file,
                                       width=int(btnWidth / 2))
        self.btnRemoveVid.grid(row=3, column=0, pady=10)

        # Button
        self.btnExportRoi = tk.Button(frameLeft, text="Export ROI for selected Video", command=self.export_roi,
                                           width=int(btnWidth / 2))
        self.btnExportRoi.grid(row=3, column=1, pady=10)

        # -------------------- Right FRAME --------------------
        self.boleanFilter = tk.IntVar()
        self.checkboxFilter = tk.Checkbutton(frameRight, text="Enable filter", variable=self.boleanFilter, command=self.onFilterChange)
        self.checkboxFilter.pack()

        self.placeholderFilter = "hue=s=0"
        self.textFilter = tk.Text(frameRight, height=3, width=btnWidth, fg="grey")
        self.textFilter.pack(padx=10, pady=10)
        self.textFilter.insert("1.0", self.placeholderFilter)
        self.textFilter.config(state=tk.DISABLED)
        self.textFilter.bind("<FocusOut>", self.onFilterFocusOut)

                # Button
        self.crop_button = tk.Button(frameRight, text="Start Cropping", command=self.crop_video, width=btnWidth)
        self.crop_button.pack(pady=10)

        # Status bar for rendering videos
        self.status_var = tk.DoubleVar()

        # Button
        self.export_settings_button = tk.Button(frameRight, text="Export Settings", command=self.export_roi_dict,
                                                width=btnWidth)
        self.export_settings_button.pack(pady=10)

        # Button
        self.export_rois_button = tk.Button(frameRight, text="Export all ROIs", command=self.export_rois,
                                            width=btnWidth)
        self.export_rois_button.pack(pady=10)

        # Button
        self.import_settings_button = tk.Button(frameRight, text="Import settings", command=self.import_roi_dict,
                                                width=btnWidth)
        self.import_settings_button.pack(pady=10)

        self.font = cv2.FONT_HERSHEY_SIMPLEX

        self.guiMenuBar()

    def guiMenuBar(self):
        menubar = tk.Menu(self.master)

        # "Datei"-Menü erstellen
        menuFile = tk.Menu(menubar, tearoff=0)
        menuFile.add_command(label="Open new video file", command=self.select_video)
        menuFile.add_command(label="Öffnen", command=self.select_video)
        menuFile.add_separator()
        menuFile.add_command(label="Beenden", command=self.select_video)
        menubar.add_cascade(label="File", menu=menuFile)

        # Filter Menu
        menuFilter = tk.Menu(menubar, tearoff=0)
        menuFilter.add_command(label="Toggle filter", command=self.toggleFilter)
        menuFilter.add_separator()
        menuFilter.add_command(label="Convert to black and white", command=lambda: self.filterAdd("hue=s=0"))
        menuFilter.add_command(label="Increase contrast and brightness", command=lambda: self.filterAdd("eq=contrast=2:brightness=0.8"))

        menubar.add_cascade(label="Filter", menu=menuFilter)

        # "Hilfe"-Menü erstellen
        hilfe_menu = tk.Menu(menubar, tearoff=0)
        hilfe_menu.add_command(label="Info", command=self.select_video)
        menubar.add_cascade(label="Hilfe", menu=hilfe_menu)

        # Menüleiste dem Hauptfenster hinzufügen
        self.master.config(menu=menubar)

    def filterAdd(self, filterString):
        self.toggleFilter(1)
        filterText = self.textFilter.get("1.0", tk.END)
        if filterString not in filterText:
            self.textFilter.insert(tk.END, f", {filterString}")

    def toggleFilter(self, state=None):
        if state is not None:
            # if state is given, change to state
            self.boleanFilter.set(state)
        else:
            self.boleanFilter.set(1 - self.boleanFilter.get())      # invert current state of filter
        self.onFilterChange()

    def onFilterChange(self):
        if self.boleanFilter.get() == 1:
            # filter activated
            self.textFilter.config(state=tk.NORMAL, fg="black")     # enable text field
        else:
            # filter deactivated
            self.textFilter.config(state=tk.DISABLED, fg="grey")    # disable and grey out

    def onFilterFocusOut(self, event):
        if self.textFilter.get("1.0", "end-1c") == "":
            self.textFilter.insert("1.0", self.placeholderFilter)
            self.textFilter.config(state=tk.DISABLED)
            self.textFilter.config(fg="grey")
            self.boleanFilter.set(0)

    def check_ffmpeg(self):
        if os.path.exists(self.ffmpeg_executable):
            try:
                # Run the command to check FFmpeg version
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)

                # Check if the command was successful
                if result.returncode == 0:
                    # Print FFmpeg version information
                    print(result.stdout)
                    return True
                else:
                    # Print the error message
                    self.show_error_message("FFmpeg Error", result.stderr, )
                    return False
            except FileNotFoundError:
                # Handle the case where ffmpeg executable is not found
                self.show_error_message("FFmpeg Error", "FFmpeg is not installed or not in the system PATH.")
                return False
        else:
            self.show_error_message("FFmpeg Error", f"ffmpeg is not installed correctly. "
                                    f"Please make sure to adjust 'ffmpeg_executable' ({self.ffmpeg_executable})")

    def select_video(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP4", ["*.mp4", "*.MP4"])])

        if not file_path:
            self.show_error_message("No Video selected", f"Error: No video selected. Please select a video.")
            return
        elif not validate_video_path(file_path):
            self.show_error_message("No Video selected", f"Error: Please select a valid video.")
            return
        else:
            # add to file list
            key = self.tree.insert("", tk.END, values=(file_path, 0, "Not labeled"))
            self.videoListByPath[file_path] = key
            # self.tree.selection_clear()         # clear selection
            # self.tree.selection_set(tk.END)                   # select the new added file

        # Clear existing ROIs for the selected video
        self.roi = []
        self.roi_dict[file_path] = []

    def remove_selected_file(self):
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0], 'values')
            video_path = item_values[0]
            self.tree.delete(selected_item[0])
            if video_path in self.roi_dict:
                self.roi_dict.pop(video_path)           # remove roi data
        else:
            self.show_error_message("No Video selected", f"Error: Please select a video.")

    def drawRoi(self):
        # information on selected video
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0], 'values')
            self.working_video_path = item_values[0]
        if not self.working_video_path:
            self.show_error_message("No Video selected", f"Error: No video selected. Please select a video.")
            return

        # Callback Function to save new rois:
        def saveNewRois(rois):
            self.roi_dict[self.working_video_path] = rois

            # Spalten Anzeige aktualisieren
            key = self.videoListByPath.get(self.working_video_path)
            if key:
                self.tree.item(key, values=(self.working_video_path, len(rois), "Labeled"))

        self.roiWindow = RoiWindow(self.master, self.roi_dict[self.working_video_path], saveCallback=saveNewRois)
        self.roiWindow.loadVideo(self.working_video_path)

    def select_output_folder(self):
        path_components = get_path_components(self.working_video_path)
        selected_folder = filedialog.askdirectory(initialdir=path_components[2])
        if not selected_folder:
            raise Exception("No folder was selected.")
        self.output_folder = selected_folder

    def crop_video(self):
        if not self.working_video_path:
            self.show_error_message("Input Video Not Selected", "Please select an input video.")
            return

        if len(self.roi_dict) < 1:
            self.show_error_message("No ROIs selected", "Please draw at least one region of interest.")
            return

        self.select_output_folder()
        if self.output_folder == "":
            self.show_error_message("No output folder selected", "Please select an output folder.")
            return

        self.status_var.set(0)  # Reset the progress bar
        self.showProgressBar()
        total_crops = sum(len(liste) for liste in self.roi_dict.values())

        rendered_video = 0

        for video_path, roi_list_per_video in self.roi_dict.items():
            if not roi_list_per_video:
                continue

            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()

            i = 0
            for roi_list in roi_list_per_video:
                start_time = 0
                i += 1

                # Cropping Filter
                x1, y1 = roi_list.getCoordinates(0)
                x2, y2 = roi_list.getCoordinates(1)
                filter = 'crop={}:{}:{}:{}'.format(x2 - x1, y2 - y1, x1, y1)

                # If black and white Checkbox is ticked:
                if self.boleanFilter.get() == 1:
                    filter += f", {self.textFilter.get("1.0", tk.END)}"

                output_filename = f"{os.path.splitext(os.path.basename(video_path))[0]}_{i}_cropped.mp4"
                subfolder = os.path.join(self.output_folder, os.path.splitext(os.path.basename(video_path))[0])
                if not os.path.exists(subfolder):
                    try:
                        os.makedirs(subfolder)
                    except Exception as e:
                        self.show_error_message("Error Creating Directory", f"Error: {e}")
                        return
                output_path = os.path.join(subfolder, output_filename)

                try:
                    ffmpeg.input(video_path, ss=start_time).output(
                        output_path,
                        vcodec='libx264',
                        crf=22,                 # quality: 22 ~ standard quality
                        vf=filter,
                        # t = duration
                    ).run(overwrite_output=True, cmd=self.ffmpeg_executable)
                    rendered_video += 1
                    # update status bar
                    progress_percent = (rendered_video / total_crops) * 100
                    self.status_var.set(progress_percent)
                    if self.status_bar:
                        self.status_bar.update()
                except Exception as e:
                    self.show_error_message("An error occurred:", f"{e} \nPlease make sure that ffmpeg is installed correctly and that the variable ffmpeg_executable contains the correct path to the file.")

            cap.release()

        if self.progress_window:
            # Progress abgeschlossen, Fenster schließen und Hauptfenster aktivieren
            self.master.attributes("-disabled", False)
            self.progress_window.destroy()

    def show_error_message(self, title, message):
        messagebox.showerror(title, message)

    def export_roi_dict(self):
        path = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")], initialfile="export.pkl")
        if path:
            with open(path, 'wb') as file:
                pickle.dump(self.roi_dict, file)

    def export_rois(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", ".csv")], initialfile="export.csv")
        if path:
            with open(path, 'w', newline='') as output_file:
                # Create a CSV writer object
                writer = csv.writer(output_file)

                for vid in self.roi_dict:
                    # Write rows to the output CSV file
                    for roi in self.roi_dict[vid]:
                        row = [vid] + roi.getCoordinates(0) + roi.getCoordinates(1)
                        writer.writerow(row)

    def import_roi_dict(self):
        path = filedialog.askopenfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")])
        if path:
            try:
                with open(path, 'rb') as file:
                    self.roi_dict = pickle.load(file)

                    for video_path, roi_list_per_video in self.roi_dict.items():
                        if not validate_video_path(video_path):
                            self.show_error_message("Video does not exist", f"Error: The importet video {video_path} does not exist.")
                            return
                        else:
                            # add to file list
                            self.listVideos.insert(tk.END, video_path)
                            self.listVideos.selection_clear(0, tk.END)  # clear selection
                            self.listVideos.selection_set(tk.END)  # select the new added file

            except Exception as e:
                self.show_error_message("Error Importing settings", f"Error: {e}")
                return

    def export_roi(self):
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0], 'values')
            self.working_video_path = item_values[0]

        if not self.working_video_path:
            self.show_error_message("No Video selected", f"Error: No video selected. Please select a video.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")],
                                            initialfile=f"{get_path_components(self.working_video_path)[0]}.pkl")
        if path:
            with open(path, 'wb') as file:
                pickle.dump(self.roi_dict[self.working_video_path], file)

    def import_roi(self):
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0], 'values')
            self.working_video_path = item_values[0]

        if not self.working_video_path:
            self.show_error_message("No Video selected", f"Error: No video selected. Please select a video.")
            return

        path = filedialog.askopenfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")])
        if path:
            try:
                with open(path, 'rb') as file:
                    self.roi_dict[self.working_video_path] = pickle.load(file)
            except Exception as e:
                self.show_error_message("Error importing ROIs", f"Error: {e}")
                return

    def showProgressBar(self):
        self.master.attributes("-disabled", True)

        self.progress_window = tk.Toplevel(self.master)
        self.progress_window.title("Progress")

        # Fortschrittsbalken erstellen
        self.status_bar = ttk.Progressbar(self.progress_window, variable=self.status_var, mode="determinate")
        self.status_bar.pack(fill=tk.X, padx=10, pady=10)


class RoiWindow:
    def __init__(self, master, roiCoordinates, saveCallback=None):
        self.window = tk.Toplevel(master)
        self.windowTitle = "Draw Region Of Interests (ROIs)"
        self.window.title(self.windowTitle)
        self.window.geometry("800x600")  # Größe des neuen Fensters

        # Tkinter-Label zum Anzeigen des Videos
        self.canvas = tk.Label(self.window)
        self.canvas.place(x=0, y=0)

        # Menu bar
        self.menubar = tk.Menu(self.window)

        self.menuFile = tk.Menu(self.menubar, tearoff=0)
        self.menuFile.add_command(label="Quit", command=self.close)
        self.menuFile.add_command(label="Save ROIs", command=self.saveRois)
        self.menubar.add_cascade(label="File", menu=self.menuFile)

        self.menuRoi = tk.Menu(self.menubar, tearoff=0)
        self.menuRoi.add_command(label="Export ROIs to file", command=self.exportRois)
        self.menuRoi.add_command(label="Import ROIS from file", command=self.importRoisFile)
        self.menuRoi.add_command(label="Import ROIS from video list")
        self.menuRoi.add_command(label="Delete all ROIs", command=lambda: self.deleteRoi(list(range(0, len(self.roiCoordinates)))))
        self.menubar.add_cascade(label="ROIs", menu=self.menuRoi)

        self.window.config(menu=self.menubar)

        # Mausklick-Event-Handler binden
        self.canvas.bind("<Button-1>", self.mouseEvent)  # Linksklick drücken
        self.canvas.bind("<ButtonRelease-1>", self.mouseEvent)  # Linksklick loslassen
        self.canvas.bind("<Button-3>", self.mouseEvent)  # Rechtsklick drücken
        self.canvas.bind("<ButtonRelease-3>", self.mouseEvent)  # Rechtsklick loslassen
        self.canvas.bind("<B1-Motion>", self.mouseEvent)  # Mausbewegung
        self.canvas.bind("<Motion>", self.mouseEvent)  # Mausbewegung
        self.canvas.bind("<Shift-Button-1>", self.mouseEvent)

        # Keyboard Event Handler
        self.window.bind("<Control-q>", self.close)
        self.window.bind("<Control-s>", self.saveRois)
        self.window.bind("<Control-a>", self.selectAll)  # Ctrl + A
        self.window.bind("<Delete>", self.delete)        # Delete
        self.window.bind("<BackSpace>", self.delete)     # Backspace (oft als Del angesehen)
        self.window.bind("<Escape>", self.escape)        # Esc

        self.defaultCursor = "crosshair"
        self.canvas.configure(cursor=self.defaultCursor)

        # Abfangen des Schließen-Ereignisses
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.frameClean = None
        self.frameWorking = None
        self.cap = None

        self.roiCoordinates = copy.deepcopy(roiCoordinates)    # deepcopy war nötig, da sonst direkt alle Änderungen gespeichert werden.
        self.newRoi = Roi()
        self.relativeCoordinates = []

        # status variables
        self.saved = True           # for exit dialog
        self.dragging = None        # for dragging a roi
        self.resizing = None        # for rezising a roi

        self.selection = []

        # store callback function
        self.saveCallback = saveCallback  # Store the callback function

    def loadVideo(self, vid_path):
        try:
            self.cap = cv2.VideoCapture(vid_path)

            if not self.cap.isOpened():
                raise ValueError("Fehler beim Öffnen des Videos.")

            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 60)  # sets cursor to 60th frame
            ret, self.frameClean = self.cap.read()  # reads frame at cursor

            if not ret:
                raise ValueError("Fehler beim Lesen des Frames.")

            # copying frame to keep it clean
            self.frameWorking = self.frameClean.copy()

            # draw existing rois:
            self.drawAllRois()

        except Exception as e:
            # Fehlerbehandlung
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}")

        finally:
            # Sicherstellen, dass das VideoCapture-Objekt geschlossen wird
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()

    def updateCanvas(self, frame):
        # Frame in RGB umwandeln
        frameRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Bild in ein PIL-Format umwandeln, das Tkinter anzeigen kann
        image = Image.fromarray(frameRGB)
        photo = ImageTk.PhotoImage(image=image)

        # Bild im Tkinter-Label anzeigen
        self.canvas.config(image=photo)
        self.canvas.image = photo

    def drawAllRois(self, params=None):
        if params is None:
            params = []
        if len(self.selection) > 0:
            for key in self.selection:
                params.append({
                    "key": key,
                    "rgb": (0, 255, 0)
                })
        print(params)

        self.frameWorking = self.frameClean.copy()
        i = 0
        for idx, roi in enumerate(self.roiCoordinates):
            result = [item["rgb"] for item in params if item["key"] == idx]
            if result:
                self.drawRoi(roi, i+1, result[0])
            else:
                self.drawRoi(roi, i+1, (255, 0, 0))
            i += 1
        self.updateCanvas(self.frameWorking)

    def drawRoi(self, roi, i, rgb=(255, 0, 0)):
        cv2.rectangle(self.frameWorking, roi.getCoordinates(0), [x + 20 for x in roi.getCoordinates(0)],
                      (255, 255, 255), -1)  # white background for text
        cv2.putText(
            self.frameWorking,
            str(i),
            [roi.getCoordinates(0)[0] + 2, roi.getCoordinates(0)[1] + 20],
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            2,
            cv2.LINE_AA)

        cv2.rectangle(self.frameWorking, roi.getCoordinates(0), roi.getCoordinates(1), rgb, 2)
        self.updateCanvas(self.frameWorking)

    def mouseEvent(self, event):
        x = event.x
        y = event.y
        if event.type == tk.EventType.ButtonPress:
            if event.num == 1:  # Linke Maustaste
                if event.state & 0x0001:  # Shift-Taste gedrückt
                    self.shiftLeftMouseDown(x, y)
                else:
                    self.saved = False
                    self.leftMouseDown(x, y)
            elif event.num == 3:  # Rechte Maustaste
                self.rightMouseDown(x, y)
        elif event.type == tk.EventType.ButtonRelease:
            if event.num == 1 and not event.state & 0x0001: # Linke Maustaste und nicht shift
                self.saved = False
                self.leftMouseUp(x, y)
            elif event.num == 3:  # Rechte Maustaste
                print("rechte taste")
        elif event.type == tk.EventType.Motion:
            if event.state == 264:
                self.leftMouseMove(x, y)
            elif event.state == 1032:
                print("Nein")
            else:
                self.mouseMove(x, y)

    def leftMouseDown(self, x, y):
        # Check if any existing rectangle is clicked
        for idx, roi in enumerate(self.roiCoordinates):
            (x1, y1), (x2, y2) = roi.getCoordinates(slice(0, 2))
            radius = 10
            if x1 - radius * 2 <= x <= x1 + radius * 2 and y1 - radius * 2 <= y <= y1 + radius * 2:
                # top-left
                self.resizing = (idx, (1, 1, 0, 0))
                self.relativeCoordinates = [x1 - x, y1 - y]
            elif x2 - radius * 2 <= x <= x2 + radius * 2 and y1 - radius * 2 <= y <= y1 + radius * 2:
                # top-right
                self.resizing = (idx, (0, 1, 1, 0))
                self.relativeCoordinates = [x2 - x, y1 - y]
            elif x1 - radius * 2 <= x <= x1 + radius * 2 and y2 - radius * 2 <= y <= y2 + radius * 2:
                # bottom-left
                self.resizing = (idx, (1, 0, 0, 1))
                self.relativeCoordinates = [x1 - x, y2 - y]
            elif x2 - radius * 2 <= x <= x2 + radius * 2 and y2 - radius * 2 <= y <= y2 + radius * 2:
                # bottom-right
                self.resizing = (idx, (0, 0, 1, 1))
                self.relativeCoordinates = [x2 - x, y2 - y]
            elif x1 - radius <= x <= x2 + radius and y1 - radius <= y <= y1 + radius:
                # top
                self.resizing = (idx, (0, 1, 0, 0))
                self.relativeCoordinates = [x, y1 - y]
            elif x1 - radius <= x <= x2 + radius and y2 - radius <= y <= y2 + radius:
                # bottom
                self.resizing = (idx, (0, 0, 0, 1))
                self.relativeCoordinates = [x, y2 - y]
            elif x1 - radius <= x <= x1 + radius and y1 - radius <= y <= y2 + radius:
                # left
                self.resizing = (idx, (1, 0, 0, 0))
                self.relativeCoordinates = [x1 - x, y]
            elif x2 - radius <= x <= x2 + radius and y1 - radius <= y <= y2 + radius:
                # right
                self.resizing = (idx, (0, 0, 1, 0))
                self.relativeCoordinates = [x2 - x, y]
            elif x1 <= x <= x2 and y1 <= y <= y2:
                self.dragging = idx
                # self.relativeCoordinates = [x1 - x, y1 - y]
        else:
            self.newRoi.setCoordinates(0, x, y, False)

        if self.resizing is not None:
            self.selection = [self.resizing[0]]
        elif self.dragging is not None:
            if self.dragging not in self.selection:
                self.selection = [self.dragging]
            self.relativeCoordinates = {}
            for idx in self.selection:
                (x1, y1), (x2, y2) = self.roiCoordinates[idx].getCoordinates(slice(0, 2))
                self.relativeCoordinates[idx] = [x1 - x, y1 - y]

        else:
            self.resetSelection()

    def leftMouseUp(self, x, y):
        if self.resizing is not None:
            self.selection.clear()
            self.resizing = None
        elif self.dragging is not None:
            self.dragging = None
        else:
            self.newRoi.setCoordinates(1, x, y, False)
            self.roiCoordinates.append(copy.deepcopy(self.newRoi))
            self.newRoi.reset()
            self.selection.clear()

        self.drawAllRois()

    def leftMouseMove(self, x, y):
        if self.dragging is not None:
            if len(self.selection) > 0:
                for idx in self.selection:
                    roi = self.roiCoordinates[idx]
                    roi.setRoi([
                        x + self.relativeCoordinates[idx][0],
                        y + self.relativeCoordinates[idx][1]
                    ], [
                        roi.getWidth() + x + self.relativeCoordinates[idx][0],
                        roi.getHeight() + y + self.relativeCoordinates[idx][1]
                    ])
        elif self.resizing is not None:
            roi = self.roiCoordinates[self.resizing[0]]
            if self.resizing[1][1] == 1:
                # top
                roi.setCoordinates(0, roi.getCoordinates(0)[0], y + self.relativeCoordinates[1], True)
            if self.resizing[1][3] == 1:
                # bottom
                roi.setCoordinates(1, roi.getCoordinates(1)[0], y + self.relativeCoordinates[1], True)
            if self.resizing[1][0] == 1:
                # left
                roi.setCoordinates(0, x + self.relativeCoordinates[0], roi.getCoordinates(0)[1], True)
            if self.resizing[1][2] == 1:
                # right
                roi.setCoordinates(1, x + self.relativeCoordinates[0], roi.getCoordinates(1)[1], True)
        else:  # when creating a new roi
            self.newRoi.setStatus(True)
            self.newRoi.setCoordinates(1, x, y, False)

        self.drawAllRois()
        if self.newRoi.getStatus():
            self.drawRoi(self.newRoi, len(self.roiCoordinates) + 1, (0, 255, 0))

    def mouseMove(self, x, y):
        hovering = False
        # changing mouse cursor when hovering
        for idx, roi in enumerate(self.roiCoordinates):
            (x1, y1), (x2, y2) = roi.getCoordinates(slice(0, 2))
            radius = 10
            if x1 - radius * 2 <= x <= x1 + radius * 2 and y1 - radius * 2 <= y <= y1 + radius * 2:
                self.canvas.configure(cursor="top_left_corner")
                hovering = True
            elif x2 - radius * 2 <= x <= x2 + radius * 2 and y1 - radius * 2 <= y <= y1 + radius * 2:
                self.canvas.configure(cursor="top_right_corner")
                hovering = True
            elif x1 - radius * 2 <= x <= x1 + radius * 2 and y2 - radius * 2 <= y <= y2 + radius * 2:
                self.canvas.configure(cursor="bottom_left_corner")
                hovering = True
            elif x2 - radius * 2 <= x <= x2 + radius * 2 and y2 - radius * 2 <= y <= y2 + radius * 2:
                self.canvas.configure(cursor="bottom_right_corner")
                hovering = True
            elif x1 - radius <= x <= x2 + radius and y1 - radius <= y <= y1 + radius:
                self.canvas.configure(cursor="top_side")
                hovering = True
            elif x1 - radius <= x <= x2 + radius and y2 - radius <= y <= y2 + radius:
                self.canvas.configure(cursor="bottom_side")
                hovering = True
            elif x1 - radius <= x <= x1 + radius and y1 - radius <= y <= y2 + radius:
                self.canvas.configure(cursor="left_side")
                hovering = True
            elif x2 - radius <= x <= x2 + radius and y1 - radius <= y <= y2 + radius:
                self.canvas.configure(cursor="right_side")
                hovering = True
            elif x1 <= x <= x2 and y1 <= y <= y2:
                self.canvas.configure(cursor="fleur")
                hovering = True

        if not hovering:
            self.canvas.configure(cursor=self.defaultCursor)

    def rightMouseDown(self, x, y):
        # Check if any existing rectangle is clicked
        for idx, roi in enumerate(self.roiCoordinates):
            (x1, y1), (x2, y2) = roi.getCoordinates(slice(0, 2))
            if x1 <= x <= x2 and y1 <= y <= y2:
                # existing Rectangle was clicked
                self.selection = [idx]
                self.drawAllRois()

                popup = tk.Menu(self.canvas, tearoff=0)

                # Hinzufügen eines "Titels" durch einen Label-artigen Menü-Eintrag
                popup.add_command(label=f"ROI #{idx + 1}", state="disabled", font=("Arial", 12, "bold"))
                popup.add_separator()
                popup.add_command(label="Delete ROI", command=lambda: self.deleteRoi(idx))
                popup.add_command(label="Display ROI dimensions", command=lambda: self.editRoi(idx))

                # Umrechnung von Canvas-Koordinaten zu Bildschirmkoordinaten
                canvas_x = self.canvas.winfo_rootx() + x
                canvas_y = self.canvas.winfo_rooty() + y

                # Menü anzeigen
                try:
                    popup.tk_popup(canvas_x, canvas_y)
                finally:
                    popup.grab_release()

    def shiftLeftMouseDown(self, x, y):
        for idx, roi in enumerate(self.roiCoordinates):
            (x1, y1), (x2, y2) = roi.getCoordinates(slice(0, 2))
            if x1 <= x <= x2 and y1 <= y <= y2:
                if idx not in self.selection:
                    self.selection.append(idx)
                    self.drawAllRois()

    def saveRois(self, params=None):
        self.saveCallback(self.roiCoordinates)
        self.saved = True

    def deleteRoi(self, key):
        if isinstance(key, int):
            self.roiCoordinates.pop(key)
        elif isinstance(key, list):
            self.roiCoordinates = [item for index, item in enumerate(self.roiCoordinates) if index not in key]
        self.resetSelection()
        self.drawAllRois()

    def editRoi(self, roiKey):
        def close():
            # Überprüfen, ob Änderungen vorgenommen wurden
            changes = [
                (key, variables[key]["value"].get())
                for key in variables
                if variables[key]["value"].get() != original_values[key]]
            if changes:
                change_message = "The following changes have been made:\n"
                for var_name, new_value in changes:
                    change_message += f"{var_name}: {new_value}\n"

                response = messagebox.askyesno("Confirm",
                                               f"Changes have been made:\n{change_message}\nDo you want to save them?")
                if response:
                    self.roiCoordinates[roiKey].setCoordinates(
                        0,
                        variables["X_1"]["value"].get(),
                        variables["Y_1"]["value"].get()
                    )
                    self.roiCoordinates[roiKey].setCoordinates(
                        1,
                        variables["X_2"]["value"].get(),
                        variables["Y_2"]["value"].get()
                    )
                    self.drawAllRois()
                else:
                    # Änderungen werden verworfen
                    print("Changes discarded.")
            else:
                print("No changes made.")

            # Schließen des Fensters
            info_window.destroy()

        # Erstellen des Toplevel-Fensters
        info_window = tk.Toplevel(self.window)
        info_window.title(f"Dimensions of ROI # {roiKey}")
        # info_window.geometry("300x400")  # Größe des Infofensters

        # Hinzufügen einer Überschrift
        header_label = tk.Label(info_window, text="Information Table", font=("Arial", 14, "bold"))
        header_label.grid(row=0, column=0, columnspan=2, pady=10)

        # Erstellen der Tabelle mit editierbaren Variablen
        variables = {
            "X_1": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getCoordinates(0)[0]),
                "editable": tk.BooleanVar(value=True)
            },
            "Y_1": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getCoordinates(0)[1]),
                "editable": tk.BooleanVar(value=True)
            },
            "X_2": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getCoordinates(1)[0]),
                "editable": tk.BooleanVar(value=True)
            },
            "Y_2": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getCoordinates(1)[1]),
                "editable": tk.BooleanVar(value=True)
            },
            "Height": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getHeight()),
                "editable": tk.BooleanVar(value=False)
            },
            "Width": {
                "value": tk.IntVar(value=self.roiCoordinates[roiKey].getWidth()),
                "editable": tk.BooleanVar(value=False)
            }
        }

        original_values = {key: var["value"].get() for key, var in variables.items()}

        row = 1
        for var_name, var_info in variables.items():
            label = tk.Label(info_window, text=var_name, anchor="w")
            entry = tk.Entry(info_window, textvariable=var_info["value"])

            # Zustand des Entry-Widgets setzen
            if var_info["editable"].get():
                entry.config(state="normal")
            else:
                entry.config(state="disabled")

            label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
            entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            row += 1

        # Hinzufügen eines Schließen-Buttons
        close_button = tk.Button(info_window, text="Close", command=close)
        close_button.grid(row=row, column=0, columnspan=2, pady=10)

    def close(self, params=None):
        if self.saved:
            self.destroy()
        else:
            if messagebox.askokcancel("ROIs not saved!", "The ROIs were not saved. Do you want to quit anyways?"):
                self.destroy()

    def destroy(self, params=None):
        self.cap.release()
        self.window.destroy()

    def importRoisFile(self):
        path = filedialog.askopenfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")])
        if path:
            try:
                with open(path, 'rb') as file:
                    if len(self.roiCoordinates) > 0:
                        # at least 1 ROI already exists
                        option = messagebox.askyesno("Choose Option", "Do you want to replace the existing ROIs?")
                        if option:
                            self.roiCoordinates = pickle.load(file)
                        else:
                            self.roiCoordinates.extend(pickle.load(file))
                    else:
                        self.roiCoordinates = pickle.load(file)
                self.drawAllRois()
            except Exception as e:
                print("Error importing ROIs", f"Error: {e}")
                return

    def exportRois(self):
        path = filedialog.asksaveasfilename(defaultextension=".pkl", filetypes=[("pickle", ".pkl")], initialfile=f"ROIs.pkl")
        if path:
            with open(path, 'wb') as file:
                pickle.dump(self.roiCoordinates, file)

    def selectAll(self, event):
        self.selection = list(range(0, len(self.roiCoordinates)))
        self.drawAllRois()

    def delete(self, event):
        self.deleteRoi(self.selection)

    def escape(self, event):
        self.resetSelection()

    def resetSelection(self):
        self.selection = []


def validate_video_path(path):
    if get_path_components(path)[1] in [".mp4", ".MP4"]:
        return True
    else:
        return False


def get_path_components(file_path):
    # Get the base name of the file from the file path
    file_name = os.path.basename(file_path)
    directory = os.path.dirname(file_path)

    # Split the file name and extension
    name, extension = os.path.splitext(file_name)

    return name, extension, directory


if __name__ == "__main__":
    debug = True
    params = {
        "ffmpeg_executable": r'ffmpeg.exe'
    }
    root = tk.Tk()
    app = VideoCropperGUI(root, params=params)
    root.mainloop()
