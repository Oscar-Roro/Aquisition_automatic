import numpy as np
import time
import os
from collections import deque
import matplotlib.pyplot as plt
from pyAndorSDK3 import AndorSDK3
plt.close("all")
timestr = time.strftime("%Y-%m-%d_%H-%M")
print("Fecha:", timestr)

add_path = "2025_10_27_01" # Additional pathing towards carpet
prismWollas = ""#  input("¿ Has puesto el prisma ? : ").strip()
estudio = "si Heat/si PBS_"

if prismWollas in ["yes", "y", "Y", "Yes", "si", "Si", "SI"]:
    grad_prismWollas = float(input("Graduación del prism (en º): "))
    estudio = "no Heat/si PBS_"

def unpack_mono12_packed(buffer, width, height):
    buffer = np.frombuffer(buffer, dtype=np.uint8)
    assert len(buffer) % 3 == 0, "El buffer no tiene un tamaño válido para Mono12Packed"

    b0 = buffer[0::3]
    b1 = buffer[1::3]
    b2 = buffer[2::3]

    pixel0 = (b0.astype(np.uint16) << 4) | (b1 & 0x0F)
    pixel1 = (b2.astype(np.uint16) << 4) | (b1 >> 4)

    pixels = np.empty(pixel0.size + pixel1.size, dtype=np.uint16)
    pixels[0::2] = pixel0
    pixels[1::2] = pixel1

    assert pixels.size == width * height, "Tamaño de imagen incompatible"
    return pixels.reshape((height, width))

def process_image(acquisition, width, height):
    raw_data = acquisition._np_data.tobytes()
    img = unpack_mono12_packed(raw_data, width, height)
    acquisition._np_data = img
    return acquisition

def custom_acquire_series(cam, frame_count = 1, width = 2150, height = 2540):
    timeout = 15000 # can determine the maximum exposure too
    cam.TriggerMode = "Software"
    cam.CycleMode = "Fixed"
    cam.FrameCount = frame_count

    imgsize = cam.ImageSizeBytes
    for _ in range(frame_count):
        buf = np.empty((imgsize,), dtype='B') # "B" es uint8
        cam.queue(buf, imgsize)

    series = deque() #¿necesario si no haces appendleft()?
    try:# start 
        cam.AcquisitionStart()  
        for frame in range(frame_count):
            cam.SoftwareTrigger()
            acq = cam.wait_buffer(timeout)
            acq = process_image(acq, width, height)
            series.append(acq)
            print(f"{(frame + 1) / frame_count * 100:.0f}% complete series", end="\r")
    finally:# stop
        cam.AcquisitionStop()
        cam.flush()
    return list(series)

def plot_and_save_first_frame(acqs, gain, exposure, gatemode, gate_width_sec,add_path):
    if not acqs:
        print("No hay frames para mostrar.")
        return
    img = acqs[0]._np_data
    fig, ax = plt.subplots(figsize=(6, 6))
    im1 = ax.imshow(img, origin = "lower", cmap='gray', vmin=100)#, vmax=4095)
    title = f"Frame 1 - {gain} gain, {exposure}s, {gatemode}"
    if gatemode == "DDG":
        title += f", {gate_width_sec:.3e}s"
    ax.set_title(title)
    fig.colorbar(im1, label='Intensidad (12 bits)')
    fig.tight_layout()

    # Guardar imagen
    title = estudio + title
    safe_title = title.replace(" ", "_").replace(",", "").replace("/", "-")
    if add_path != "":
        add_path = f"{add_path}//"
    img_path = f"acqui-pics//{add_path}{safe_title}_{timestr}.png"
    plt.savefig(img_path)
    #plt.show()
    print(f"Imagen guardada como {img_path}")

def save_frames(acqs, gain, frames, exposure, gatemode, gate_width_sec,add_path):
    imgs = np.stack([acq._np_data for acq in acqs]) #imgs.shape = (N, H, W)
    name = f"gn{gain}_n{frames}_t{exposure}_gate_{gatemode}"
    if gatemode == "DDG":
        name += f"_width{gate_width_sec:.2e}"
    name = name.replace(".", "p")
    if add_path != "":
        add_path = f"{add_path}//"
    path = f"acqui-pics//{add_path}" + name + "_" + timestr + ".npz"
    np.savez_compressed(path, images=imgs)
    print(f"Frames guardados en {os.path.abspath(path)}")

def main():
    
    # --- Parameter sweeps --- Use LISTS
    exposure_times_s = [2.5e-3] # seconds
    gate_widths_s = [5e-9] # seconds
    gains =  [4095] # int
    frame_count = 10 # int
    # --- Create Camera Object  
    sdk3 = AndorSDK3()
    cam = sdk3.GetCamera(0)
    print("Cámara conectada:", cam.SerialNumber)
    # Cooldown camera
    cam.SensorCooling = True
    while cam.SensorTemperature > 2.0:
        print(f"Temperature: {cam.SensorTemperature:.2f}C")
        if cam.TemperatureStatus == "Fault":
            raise RuntimeError("Fallo en la refrigeración del sensor")
        time.sleep(5)
    print("Sensor estabilizado.")
    # Configure Gating Mode
    cam.GateMode = "DDG"
    gatemode = cam.GateMode
    print(f"Test to know size {cam.ImageSizeBytes}") 
    cam.AOIHeight = 900 #2150 #2160
    cam.AOIWidth = 1500 #2540 #2560
    cam.AOITop = 100 #1
    cam.AOILeft = 400 #1
    cam.PixelEncoding = "Mono12Packed"
    cam.FrameRate = cam.max_FrameRate
    # Set Camera Variables 
    width, height = cam.AOIWidth, cam.AOIHeight
    gain_target = cam.MCPGain
    # --- Start Acquisitions, saved as LIST in 'acqs' variable
    acqs = custom_acquire_series(cam, frame_count, width, height)
    print("\n Adquisición completada.")
    # --- Loop process in case you want to sweep through multiple parameters
    total_runs = len(exposure_times_s) * len(gate_widths_s) * len(gains)
    run = 1
    for _gain in gains:
        cam.MCPGain = _gain
        for _exposure_time_s in exposure_times_s:
            for _gate_width_s in gate_widths_s:
                _gate_width_ps = int(_gate_width_s * 1e12) # convertir a picosegundos
                cam.DDGOpticalWidthEnable = True #don't know if this needs to be in the loop or outside
                cam.DDGOutputWidth = _gate_width_ps
                print(f"DDGOutputWidth configurado a {_gate_width_ps} ps")
                print(f"\n--- Run {run}/{total_runs} ---")
                print(f"Gain: {_gain}, Exposure: {_exposure_time_s}s, Gate width: {_gate_width_ps}ps")
                
                acqs = custom_acquire_series(cam, frame_count, width, height)
                plot_and_save_first_frame(acqs, _gain, _exposure_time_s, gatemode, _gate_width_s,add_path)
                save_frames(acqs, _gain, frame_count, _exposure_time_s, gatemode, _gate_width_s,add_path)
                run += 1
                time.sleep(2)  # Optional pause between runs
    print("\nTodas las adquisiciones completadas exitosamente.")

if __name__ == "__main__":
    main()
    plt.show()
