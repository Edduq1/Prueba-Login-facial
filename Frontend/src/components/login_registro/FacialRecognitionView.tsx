// src/components/Dashboard/FacialRecognitionView.tsx
import React, { useState } from 'react';
import { useFaceCapture } from '../../auth/hook/useFaceCapture'; 
import { loginFacial } from '../../service/api';

interface FacialRecognitionViewProps {
  isLoading: boolean;
  onGoBack: () => void;
  onRecognized: (tokens: { access: string; refresh: string }, user: any) => void;
}

const FacialRecognitionView: React.FC<FacialRecognitionViewProps> = ({ isLoading, onGoBack, onRecognized }) => {
  const { videoRef, overlayRef, faceReady, status, capture } = useFaceCapture();
  const [localLoading, setLocalLoading] = useState(false);
  const busy = isLoading || localLoading;

  const handleValidate = async () => {
    if (!faceReady || busy) return;
    const shot = capture();
    if (!shot) return;
    try {
      setLocalLoading(true);
      const resp = await loginFacial(shot.imageB64);
      const tokens = resp?.tokens;
      const user = resp?.user;
      if (tokens?.access) {
        localStorage.setItem('accessToken', tokens.access);
        if (tokens.refresh) localStorage.setItem('refreshToken', tokens.refresh);
        localStorage.setItem('user', JSON.stringify(user || {}));
      }
      onRecognized(tokens, user);
    } catch (e) {
      console.error(e);
      alert('No se pudo validar el rostro. Intente nuevamente.');
    } finally {
      setLocalLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center">
      <h2 className="text-2xl font-bold text-white mb-3">Reconocimiento Facial</h2>
      <p className="text-gray-400 text-sm mb-5">Mire directamente a la cámara.</p>

      <div className="relative w-[320px] h-[320px] rounded-full overflow-hidden border-[3px] border-blue-500/60 shadow-[0_0_40px_rgba(59,130,246,0.3)] flex items-center justify-center mb-6">
        {/* VIDEO */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="object-cover w-full h-full"
          style={{ transform: 'scaleX(-1)' }}
        />
        
        {/* OVERLAY con máscara facial */}
        <canvas
          ref={overlayRef}
          className="absolute inset-0 object-cover w-full h-full pointer-events-none"
          style={{ transform: 'scaleX(-1)' }}
        />

        {/* Efectos visuales de animación */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 border-[2px] border-blue-400/50 rounded-full animate-pulse"></div>
          {/* Línea de escaneo animada */}
          <div className="absolute inset-x-10 top-1/2 h-[2px] bg-gradient-to-r from-blue-300 via-white to-blue-300 animate-pulse" />
        </div>
      </div>

      {/* Estado */}
      <div className="text-sm text-gray-300 mb-4">{status}</div>

      {/* Botones */}
      <div className="flex gap-3">
        <button
          onClick={onGoBack}
          disabled={busy}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${busy ? 'bg-gray-300 text-gray-600' : 'bg-gray-700 text-white hover:bg-gray-600'}`}
        >
          Volver
        </button>
        <button
          onClick={handleValidate}
          disabled={!faceReady || busy}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
            faceReady && !busy ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-300 text-gray-500'
          }`}
        >
          {busy ? 'Validando...' : 'Validar rostro'}
        </button>
      </div>
    </div>
  );
};

export default FacialRecognitionView;