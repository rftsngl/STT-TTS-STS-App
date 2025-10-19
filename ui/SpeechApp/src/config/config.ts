/**
 * Application Configuration
 * Centralized configuration for the TR Speech Stack mobile app
 */

export const API_CONFIG = {
  // Base URLs for different environments
  DEVELOPMENT: {
    ANDROID: 'http://10.0.2.2:8000',
    IOS: 'http://localhost:8000',
    PHYSICAL_DEVICE: 'http://YOUR_LOCAL_IP:8000', // Update with your server IP in Settings
  },
  PRODUCTION: {
    BASE_URL: 'https://api.yourdomain.com',
  },
};

// API Keys are now stored securely using AsyncStorage
// See src/api/client.ts for API key management functions

export const TIMEOUTS = {
  REQUEST: 30000, // 30 seconds
  UPLOAD: 60000, // 60 seconds
  DOWNLOAD: 60000, // 60 seconds
};

export const LIMITS = {
  MAX_AUDIO_DURATION: 900, // 15 minutes in seconds
  MAX_TEXT_LENGTH: 5000,
  MAX_FILE_SIZE: 20 * 1024 * 1024, // 20 MB
};

export const AUDIO_CONFIG = {
  SAMPLE_RATE: 16000,
  CHANNELS: 1,
  BIT_DEPTH: 16,
  FORMAT: 'wav',
};

export const TTS_CONFIG = {
  DEFAULT_LANGUAGE: 'tr',
  DEFAULT_OUTPUT_FORMAT: 'mp3_22050_32',
  DEFAULT_STABILITY: 0.5,
  DEFAULT_SIMILARITY_BOOST: 0.75,
};

export const STT_CONFIG = {
  DEFAULT_LANGUAGE: 'tr',
  DEFAULT_TIMESTAMPS: 'words',
};

export const UI_CONFIG = {
  COLORS: {
    // Primary Colors
    PRIMARY: '#007AFF',
    PRIMARY_DARK: '#0051D5',
    PRIMARY_LIGHT: '#4DA2FF',
    PRIMARY_GRADIENT_START: '#007AFF',
    PRIMARY_GRADIENT_END: '#0051D5',

    // Accent Colors
    ACCENT: '#5856D6',
    ACCENT_LIGHT: '#7B79E8',

    // Status Colors
    SUCCESS: '#34C759',
    SUCCESS_LIGHT: '#E8F8ED',
    ERROR: '#FF3B30',
    ERROR_LIGHT: '#FFE8E8',
    WARNING: '#FF9500',
    WARNING_LIGHT: '#FFF4E5',
    INFO: '#5AC8FA',
    INFO_LIGHT: '#E5F7FF',

    // Background Colors
    BACKGROUND: '#F2F2F7',
    BACKGROUND_SECONDARY: '#FFFFFF',
    CARD_BACKGROUND: '#FFFFFF',
    OVERLAY: 'rgba(0, 0, 0, 0.5)',

    // Text Colors
    TEXT_PRIMARY: '#000000',
    TEXT_SECONDARY: '#666666',
    TEXT_TERTIARY: '#999999',
    TEXT_INVERSE: '#FFFFFF',
    TEXT_DISABLED: '#C7C7CC',

    // Border Colors
    BORDER: '#E0E0E0',
    BORDER_LIGHT: '#F0F0F0',
    BORDER_DARK: '#C7C7CC',

    // Shadow Colors
    SHADOW: '#000000',

    // Recording/Audio Colors
    RECORDING: '#FF3B30',
    RECORDING_LIGHT: '#FFE8E8',
    AUDIO_WAVE: '#007AFF',
  },

  SPACING: {
    XXS: 2,
    XS: 4,
    SM: 8,
    MD: 12,
    LG: 16,
    XL: 20,
    XXL: 24,
    XXXL: 32,
  },

  BORDER_RADIUS: {
    XS: 4,
    SM: 6,
    MD: 8,
    LG: 12,
    XL: 16,
    XXL: 20,
    ROUND: 999,
  },

  TYPOGRAPHY: {
    FONT_SIZE: {
      XXS: 10,
      XS: 11,
      SM: 12,
      MD: 14,
      LG: 16,
      XL: 18,
      XXL: 20,
      XXXL: 24,
      HUGE: 32,
    },
    FONT_WEIGHT: {
      REGULAR: '400' as const,
      MEDIUM: '500' as const,
      SEMIBOLD: '600' as const,
      BOLD: '700' as const,
    },
    LINE_HEIGHT: {
      TIGHT: 1.2,
      NORMAL: 1.5,
      RELAXED: 1.75,
    },
  },

  SHADOWS: {
    NONE: {
      shadowColor: 'transparent',
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0,
      shadowRadius: 0,
      elevation: 0,
    },
    SM: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.05,
      shadowRadius: 2,
      elevation: 1,
    },
    MD: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 3,
    },
    LG: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.15,
      shadowRadius: 8,
      elevation: 5,
    },
    XL: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.2,
      shadowRadius: 16,
      elevation: 8,
    },
  },

  ANIMATIONS: {
    DURATION: {
      FAST: 150,
      NORMAL: 250,
      SLOW: 350,
      VERY_SLOW: 500,
    },
    EASING: {
      EASE_IN: 'ease-in',
      EASE_OUT: 'ease-out',
      EASE_IN_OUT: 'ease-in-out',
      LINEAR: 'linear',
    },
  },

  TOUCH_TARGET: {
    MIN_SIZE: 44, // Minimum touch target size for accessibility
  },
};

export const FEATURE_FLAGS = {
  ENABLE_STT: true,
  ENABLE_TTS: true,
  ENABLE_VOICE_CLONING: false, // TODO: Implement
  ENABLE_AUDIO_ISOLATION: false, // TODO: Implement
  ENABLE_OFFLINE_MODE: false, // TODO: Implement
};

