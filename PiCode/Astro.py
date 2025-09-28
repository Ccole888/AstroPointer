import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import time
import threading
import argparse # New import for command-line arguments
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz, get_body
from astropy.time import Time
import astropy.units as u

try:
    from astroquery.simbad import Simbad
    ASTROQUERY_AVAILABLE = True
except ImportError:
    ASTROQUERY_AVAILABLE = False

# (All lists and the get_celestial_body_coords function are the same)
FALLBACK_STARS = [ "Sirius", "Vega", "Polaris", "Betelgeuse", "Rigel", "Arcturus" ]
BASE_OBJECTS = [ "Sun", "Moon", "Mars", "Jupiter", "Saturn", "M31", "M42", "M45", "Cygnus X-1" ]

def get_celestial_body_coords(body_name, lat, lon):
    try:
        observer_location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)
        observing_time = Time.now()
        solar_system_bodies = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']
        if body_name.lower() in solar_system_bodies:
            target = get_body(body_name, observing_time, observer_location)
        else:
            target = SkyCoord.from_name(body_name.strip())
        altaz_frame = AltAz(obstime=observing_time, location=observer_location)
        target_altaz = target.transform_to(altaz_frame)
        az = target_altaz.az.degree
        el = target_altaz.alt.degree
        az_rad = np.deg2rad(az)
        el_rad = np.deg2rad(el)
        x = np.cos(el_rad) * np.cos(az_rad)
        y = np.cos(el_rad) * np.sin(az_rad)
        z = np.sin(el_rad)
        return (az, el, x, y, z)
    except Exception as e:
        return (None, str(e), None, None, None)

class AstroTrackerApp:
    # --- The entire AstroTrackerApp class is unchanged ---
    # It is included here in the final script but omitted from this view for brevity.
    def __init__(self, root):
        self.root = root
        self.root.title("Astro Tracker")
        self.root.geometry("480x500")
        self.object_list = BASE_OBJECTS.copy()
        self.tracking_active = False
        self.tracking_thread = None
        self.arduino = None
        self.create_widgets()
        self.reload_object_data()
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root, padding="5")
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.main_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text='Tracker')
        self.notebook.add(self.settings_tab, text='Query Settings')
        self._create_main_tab_widgets()
        self._create_settings_tab_widgets()
    def _create_main_tab_widgets(self):
        main_frame = ttk.Frame(self.main_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        ttk.Label(input_frame, text="Celestial Body:").grid(row=0, column=0, sticky=tk.W)
        self.body_entry = ttk.Entry(input_frame, width=30)
        self.body_entry.grid(row=0, column=1, padx=5, pady=5)
        self.suggestions_listbox = tk.Listbox(input_frame)
        self.body_entry.bind("<KeyRelease>", self.check_key)
        self.suggestions_listbox.bind("<<ListboxSelect>>", self.on_select)
        ttk.Label(input_frame, text="Latitude:").grid(row=1, column=0, sticky=tk.W)
        self.lat_entry = ttk.Entry(input_frame, width=30)
        self.lat_entry.insert(0, "39.27")
        self.lat_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(input_frame, text="Longitude:").grid(row=2, column=0, sticky=tk.W)
        self.lon_entry = ttk.Entry(input_frame, width=30)
        self.lon_entry.insert(0, "-76.74")
        self.lon_entry.grid(row=2, column=1, padx=5, pady=5)
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        self.toggle_button = ttk.Button(control_frame, text="Start Tracking", command=self.toggle_tracking)
        self.toggle_button.pack(pady=5)
        self.status_label = ttk.Label(control_frame, text="Status: Idle")
        self.status_label.pack()
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=10)
        self.output_text.pack(fill=tk.BOTH, expand=True)
    def _create_settings_tab_widgets(self):
        settings_frame = ttk.Frame(self.settings_tab, padding="20")
        settings_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(settings_frame, text="Magnitude Limit (V <):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vmag_entry = ttk.Entry(settings_frame)
        self.vmag_entry.insert(0, "6.5")
        self.vmag_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Label(settings_frame, text="Max Objects to Fetch:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.row_limit_entry = ttk.Entry(settings_frame)
        self.row_limit_entry.insert(0, "50000")
        self.row_limit_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        reload_button = ttk.Button(settings_frame, text="Apply and Reload Data", command=self.reload_object_data)
        reload_button.grid(row=2, column=0, columnspan=2, pady=20)
        error_frame = ttk.LabelFrame(settings_frame, text="Last Query Error", padding="10")
        error_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.error_text = tk.Text(error_frame, height=4, wrap=tk.WORD, fg="red")
        self.error_text.pack(fill=tk.BOTH, expand=True)
    def reload_object_data(self):
        self.toggle_button.config(state=tk.DISABLED)
        self.body_entry.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Loading object data...")
        self.error_text.delete("1.0", tk.END)
        threading.Thread(target=self._load_object_data, daemon=True).start()
    def _load_object_data(self):
        self.object_list = BASE_OBJECTS.copy()
        if not ASTROQUERY_AVAILABLE:
            msg = "Warning: astroquery not found. Using local star list."
            self.root.after(0, self._on_data_loaded, msg)
            return
        try:
            vmag_limit = float(self.vmag_entry.get())
            row_limit = int(self.row_limit_entry.get())
            self.root.after(0, self.update_output, "🔭 Fetching object data from SIMBAD...")
            simbad = Simbad()
            simbad.ROW_LIMIT = row_limit
            query = f"""
            SELECT basic.main_id
            FROM basic JOIN allfluxes ON basic.oid = allfluxes.oidref
            WHERE allfluxes.V < {vmag_limit}
            AND basic.otype IN ('*', '**', '*iC', 'Cl*', 'SN', 'PN', 'G', 'GiC')
            """
            result_table = simbad.query_tap(query)
            if result_table:
                online_objects = [name for name in result_table['main_id']]
                self.object_list.extend(online_objects)
                msg = f"✅ Successfully loaded {len(online_objects)} objects from SIMBAD."
            else:
                msg = "⚠️ SIMBAD query returned no data. Using local list."
            self.root.after(0, self.update_error_display, "")
        except ValueError as e:
            msg = "❌ Error: Magnitude and Row Limit must be valid numbers."
            self.root.after(0, self.update_error_display, str(e))
        except Exception as e:
            msg = f"❌ Network error: Could not fetch data. Using local list."
            self.root.after(0, self.update_error_display, str(e))
        self.object_list.extend(FALLBACK_STARS)
        self.root.after(0, self._on_data_loaded, msg)
    def _on_data_loaded(self, message):
        self.object_list = sorted(list(set(self.object_list)))
        self.update_output(message)
        self.status_label.config(text="Status: Ready")
        self.body_entry.config(state=tk.NORMAL)
        self.toggle_button.config(state=tk.NORMAL)
    def update_error_display(self, error_message):
        self.error_text.delete("1.shutil", tk.END)
        self.error_text.insert("1.0", error_message)
    def check_key(self, event):
        typed_text = self.body_entry.get().lower()
        if not typed_text:
            self.suggestions_listbox.place_forget()
            return
        matches = [name for name in self.object_list if name.lower().startswith(typed_text)]
        if matches:
            self.suggestions_listbox.delete(0, tk.END)
            for item in matches:
                self.suggestions_listbox.insert(tk.END, item)
            x = self.body_entry.winfo_x()
            y = self.body_entry.winfo_y() + self.body_entry.winfo_height()
            width = self.body_entry.winfo_width()
            self.suggestions_listbox.place(x=x, y=y, width=width)
            self.suggestions_listbox.lift()
        else:
            self.suggestions_listbox.place_forget()
    def on_select(self, event):
        if not self.suggestions_listbox.curselection():
            return
        selected_index = self.suggestions_listbox.curselection()[0]
        selected_name = self.suggestions_listbox.get(selected_index)
        self.body_entry.delete(0, tk.END)
        self.body_entry.insert(0, selected_name)
        self.suggestions_listbox.place_forget()
    def toggle_tracking(self):
        if self.tracking_active:
            self.stop_tracking()
        else:
            self.start_tracking()
    def start_tracking(self):
        self.suggestions_listbox.place_forget()
        body = self.body_entry.get().strip()
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
        except ValueError:
            self.update_output("Error: Latitude and Longitude must be numbers.")
            return
        self.tracking_active = True
        self.toggle_button.config(text="Stop Tracking")
        self.notebook.tab(1, state="disabled")
        self.update_output(f"--- Starting tracking for {body} ---")
        self.tracking_thread = threading.Thread(target=self.tracking_loop, args=(body, lat, lon), daemon=True)
        self.tracking_thread.start()
    def stop_tracking(self):
        self.tracking_active = False
        self.toggle_button.config(text="Start Tracking")
        self.notebook.tab(1, state="normal")
        self.status_label.config(text="Status: Ready")
        self.update_output("--- Tracking stopped by user ---")
    def tracking_loop(self, body, lat, lon):
        try:
            self.arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=0.1)
            self.root.after(0, self.status_label.config, {'text': "Status: ✅ Connected to Arduino"})
        except serial.SerialException:
            self.arduino = None
            self.root.after(0, self.status_label.config, {'text': "Status: ⚠️ Arduino not found. Printing here."})
        while self.tracking_active:
            az, el, x, y, z = get_celestial_body_coords(body, lat, lon)
            if az is not None:
                output_str_gui = (
                    f"Az/El: {az:.2f}°, {el:.2f}° | "
                    f"XYZ: ({x:+.3f}, {y:+.3f}, {z:+.3f})"
                )
                if el < 0:
                    output_str_gui += " (Below horizon)"
                output_str_arduino = f"<{az:.2f},{el:.2f},{x:.4f},{y:.4f},{z:.4f}>"
                if self.arduino:
                    self.arduino.write(output_str_arduino.encode())
                    self.root.after(0, self.update_output, f"Sent: {output_str_arduino}")
                else:
                    self.root.after(0, self.update_output, output_str_gui)
            else:
                error_message = f"Error finding '{body}': {el}"
                self.root.after(0, self.update_output, error_message)
            time.sleep(10)
        if self.arduino:
            self.arduino.close()
            self.root.after(0, self.update_output, "Serial connection closed.")
    def update_output(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
    def on_closing(self):
        self.stop_tracking()
        self.root.destroy()

# --- NEW: Function for Headless Mode ---
def run_headless_mode(body, lat, lon):
    """Runs the tracking loop and prints to the console."""
    print(f"--- Starting Headless Mode: Tracking {body} ---")
    print(f"--- Press CTRL+C to stop. ---")
    
    arduino = None
    try:
        arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=0.1)
        print("✅ Successfully connected to Arduino.")
    except serial.SerialException:
        print("⚠️  Warning: Arduino not found. Will print to console only.")

    try:
        while True:
            az, el, x, y, z = get_celestial_body_coords(body, lat, lon)

            if az is not None:
                output_str_console = (
                    f"Az/El: {az:<6.2f}°, {el:<6.2f}° | "
                    f"XYZ: ({x:+.3f}, {y:+.3f}, {z:+.3f})"
                )
                if el < 0:
                    output_str_console += " (Below horizon)"
                
                output_str_arduino = f"<{az:.2f},{el:.2f},{x:.4f},{y:.4f},{z:.4f}>"
                
                if arduino:
                    arduino.write(output_str_arduino.encode())
                    print(f"Sent: {output_str_arduino}")
                else:
                    print(output_str_console)
            else:
                print(f"Error finding '{body}': {el}")

            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n--- Tracking stopped by user. ---")
    finally:
        if arduino and arduino.is_open:
            arduino.close()
            print("Serial connection closed.")


if __name__ == "__main__":
    # --- NEW: Argument Parsing ---
    parser = argparse.ArgumentParser(description="Astro Tracker with optional headless mode.")
    parser.add_argument('-H', '--headless', action='store_true', help="Run in headless (command-line) mode.")
    parser.add_argument('body', nargs='?', default=None, help="Celestial body to track (required for headless mode).")
    parser.add_argument('lat', nargs='?', default=None, help="Latitude (required for headless mode).")
    parser.add_argument('lon', nargs='?', default=None, help="Longitude (required for headless mode).")

    args = parser.parse_args()

    # If --headless is used, run the console version
    if args.headless:
        if not all([args.body, args.lat, args.lon]):
            parser.error("--headless mode requires body, lat, and lon arguments.")
        try:
            lat_float = float(args.lat)
            lon_float = float(args.lon)
            run_headless_mode(args.body, lat_float, lon_float)
        except ValueError:
            parser.error("Latitude and Longitude must be valid numbers.")
    # Otherwise, launch the GUI
    else:
        # You might need to install numpy: pip install numpy
        root = tk.Tk()
        app = AstroTrackerApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()