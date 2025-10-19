import apiClient from './client';
import { AxiosError } from 'axios';

// Types
export interface STTResponse {
  text: string;
  language: string;
  duration: number;
  segments: Array<{
    id: number;
    start: number;
    end: number;
    text: string;
  }>;
  words?: Array<{
    word: string;
    start: number;
    end: number;
    probability: number;
  }>;
}

export interface TTSRequest {
  text: string;
  voice_id?: string;
  voice_alias?: string;
  model_id?: string;
  output_format?: string;
  language?: string;
  stability?: number;
  similarity_boost?: number;
}

export interface Voice {
  voice_id: string;
  name: string;
  category?: string;
  description?: string;
  labels?: Record<string, string>;
  source: string;
}

export interface VoicesResponse {
  voices: Voice[];
}

export interface HealthResponse {
  status: string;
  device: string;
  features: Record<string, boolean | string>;
  metrics: {
    count: number;
    avg_total_ms: number;
    avg_stt_ms: number;
  };
}

// STT Service
export const sttService = {
  transcribe: async (audioFile: {
    uri: string;
    type: string;
    name: string;
  }, language: string = 'tr'): Promise<STTResponse> => {
    const formData = new FormData();
    formData.append('audio_file', audioFile as any);
    formData.append('language', language);
    formData.append('timestamps', 'words');

    try {
      const response = await apiClient.post<STTResponse>('/stt', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      throw handleApiError(error);
    }
  },
};

// TTS Service
export const ttsService = {
  synthesize: async (request: TTSRequest): Promise<Blob> => {
    try {
      const response = await apiClient.post('/tts', request, {
        responseType: 'blob',
      });
      return response.data;
    } catch (error) {
      throw handleApiError(error);
    }
  },
};

// Voices Service
export const voicesService = {
  getVoices: async (): Promise<VoicesResponse> => {
    try {
      const response = await apiClient.get<VoicesResponse>('/voices');
      return response.data;
    } catch (error) {
      throw handleApiError(error);
    }
  },

  createAlias: async (alias: string, voiceId: string, name: string) => {
    try {
      const response = await apiClient.post('/voices/aliases', {
        alias,
        voice_id: voiceId,
        name,
      });
      return response.data;
    } catch (error) {
      throw handleApiError(error);
    }
  },

  deleteAlias: async (alias: string) => {
    try {
      await apiClient.delete(`/voices/aliases/${alias}`);
    } catch (error) {
      throw handleApiError(error);
    }
  },
};

// Health Service
export const healthService = {
  check: async (): Promise<HealthResponse> => {
    try {
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    } catch (error) {
      throw handleApiError(error);
    }
  },
};

// Error Handler
export const handleApiError = (error: any): Error => {
  if (error.response) {
    const { status, data } = error.response;
    const errorCode = data?.code || 'UNKNOWN_ERROR';
    const message = data?.detail || data?.message || 'Unknown error';

    switch (status) {
      case 400:
        return new Error(`Invalid request (${errorCode}): ${message}`);
      case 401:
        return new Error('⚠️ API key required. Please add your ElevenLabs API key in Settings.');
      case 413:
        return new Error('Audio file too long (max 15 minutes)');
      case 422:
        return new Error(`Validation error (${errorCode}): ${message}`);
      case 429:
        return new Error('Too many requests, please wait');
      case 500:
        if (errorCode === 'SAVE_FAILED') {
          return new Error('⚠️ Failed to save API key. Please try again.');
        }
        return new Error(`Server error: ${message}`);
      case 501:
        if (errorCode === 'TTS_NOT_CONFIGURED') {
          return new Error('⚠️ ElevenLabs API key not configured. Please add your API key in Settings.');
        }
        return new Error(`Not implemented: ${message}`);
      case 503:
        if (errorCode === 'STT_UNAVAILABLE') {
          return new Error('⚠️ Speech-to-Text service unavailable. Please try again later.');
        }
        return new Error('Service unavailable');
      case 507:
        return new Error('Request timeout');
      default:
        return new Error(`Server error (${status}): ${message}`);
    }
  } else if (error.request) {
    return new Error('No response from server. Please check your connection and server URL in Settings.');
  }
  return new Error(error.message || 'Unknown error');
};

