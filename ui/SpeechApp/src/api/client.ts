import axios, { AxiosInstance, AxiosError } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../config/config';
import { getApiBaseUrl } from '../utils/helpers';

// Storage keys
export const STORAGE_KEYS = {
  ELEVENLABS_API_KEY: 'elevenlabs_api_key',
  SERVER_URL: 'server_url',
};

// API Base URL Configuration
const getBaseURL = async (): Promise<string> => {
  // Check if user has set a custom server URL
  const customUrl = await AsyncStorage.getItem(STORAGE_KEYS.SERVER_URL);
  if (customUrl) {
    return customUrl;
  }
  // Use default URL based on platform
  return getApiBaseUrl();
};

// Get API key from secure storage
export const getApiKey = async (): Promise<string | null> => {
  return await AsyncStorage.getItem(STORAGE_KEYS.ELEVENLABS_API_KEY);
};

// Save API key to secure storage
export const saveApiKey = async (apiKey: string): Promise<void> => {
  await AsyncStorage.setItem(STORAGE_KEYS.ELEVENLABS_API_KEY, apiKey);
};

// Remove API key from secure storage
export const removeApiKey = async (): Promise<void> => {
  await AsyncStorage.removeItem(STORAGE_KEYS.ELEVENLABS_API_KEY);
};

// Save server URL to storage
export const saveServerUrl = async (url: string): Promise<void> => {
  await AsyncStorage.setItem(STORAGE_KEYS.SERVER_URL, url);
};

// Get server URL from storage
export const getServerUrl = async (): Promise<string | null> => {
  return await AsyncStorage.getItem(STORAGE_KEYS.SERVER_URL);
};

// Create API Client
export const apiClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(), // Initial base URL (will be updated by interceptor)
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor to add API key and update base URL
apiClient.interceptors.request.use(
  async (config) => {
    // Update base URL from storage if available
    const baseURL = await getBaseURL();
    config.baseURL = baseURL;

    // Add ElevenLabs API key if available
    const apiKey = await getApiKey();
    if (apiKey) {
      config.headers['X-ElevenLabs-Key'] = apiKey;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const { status, data } = error.response;
      console.error(`API Error [${status}]:`, data);
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default apiClient;

