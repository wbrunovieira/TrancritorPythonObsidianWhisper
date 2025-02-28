import sounddevice as sd
import wavio
import os
import numpy as np
from config import AUDIO_DIRECTORY  # Certifique-se de que AUDIO_DIRECTORY está configurado corretamente

def select_device():
    """
    Lista os dispositivos disponíveis e solicita que o usuário selecione o índice desejado.
    """
    devices = sd.query_devices()
    print("Dispositivos disponíveis:")
    for i, device in enumerate(devices):
        name = device.get('name', 'Unknown')
        max_in = device.get('max_input_channels', 0)
        max_out = device.get('max_output_channels', 0)
        print(f"{i}: {name} ({max_in} in, {max_out} out)")
    
    while True:
        try:
            selected = int(input("👉 Selecione o índice do dispositivo desejado: "))
            if 0 <= selected < len(devices):
                return selected
            else:
                print("❌ Índice inválido. Tente novamente.")
        except ValueError:
            print("❌ Entrada inválida. Por favor, digite um número.")

def record_system_audio_until_stop(fs=44100, channels=2, filename="system_audio.wav"):
    """
    Grava o áudio do sistema indefinidamente até que o usuário pressione 's' e Enter.
    
    Parâmetros:
      fs (int): taxa de amostragem (padrão 44100 Hz).
      channels (int): número de canais desejados (padrão 2).
      filename (str): nome do arquivo de áudio a ser salvo.
      
    Retorna:
      file_path (str): caminho completo para o arquivo de áudio gravado.
    """

    while True:
        device_index = select_device()
        device_info = sd.query_devices(device_index)
        max_input_channels = device_info.get('max_input_channels', 0)
        if max_input_channels < 1:
            print("❌ O dispositivo selecionado não possui canais de entrada. Por favor, selecione outro dispositivo.")
        else:
            if channels > max_input_channels:
                print(f"⚠️ O dispositivo suporta apenas {max_input_channels} canal(is). Ajustando para {max_input_channels}.")
                channels = max_input_channels
            break

    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            print(status)
        frames.append(indata.copy())

    print("🎙️ Gravando áudio... Pressione 's' e Enter para parar a gravação.")
    with sd.InputStream(callback=callback, samplerate=fs, channels=channels, device=device_index):
        # Aguardando o comando para parar a gravação
        while True:
            if input().strip().lower() == 's':
                break

    # Concatena todos os blocos de áudio gravados
    all_data = np.concatenate(frames, axis=0)
    file_path = os.path.join(AUDIO_DIRECTORY, filename)
    wavio.write(file_path, all_data, fs, sampwidth=2)
    print(f"🔊 Áudio salvo em: {file_path}")
    return file_path