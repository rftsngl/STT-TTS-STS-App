import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Platform,
  Animated,
  RefreshControl,
} from 'react-native';
import { getApiKey, saveApiKey, removeApiKey, getServerUrl, saveServerUrl } from '../api/client';
import { validateElevenLabsKey } from '../utils/helpers';
import { UI_CONFIG } from '../config/config';
import {
  AnimatedCard,
  AnimatedButton,
  LoadingSpinner,
} from '../components';

export const SettingsScreen: React.FC = () => {
  const [apiKey, setApiKey] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const successAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadSettings();
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: UI_CONFIG.ANIMATIONS.DURATION.NORMAL,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    if (saveSuccess) {
      Animated.sequence([
        Animated.timing(successAnim, {
          toValue: 1,
          duration: UI_CONFIG.ANIMATIONS.DURATION.FAST,
          useNativeDriver: true,
        }),
        Animated.delay(2000),
        Animated.timing(successAnim, {
          toValue: 0,
          duration: UI_CONFIG.ANIMATIONS.DURATION.FAST,
          useNativeDriver: true,
        }),
      ]).start(() => setSaveSuccess(false));
    }
  }, [saveSuccess]);

  const loadSettings = async () => {
    try {
      setIsLoading(true);
      const savedApiKey = await getApiKey();
      const savedServerUrl = await getServerUrl();

      if (savedApiKey) {
        setApiKey(savedApiKey);
      }
      if (savedServerUrl) {
        setServerUrl(savedServerUrl);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      Alert.alert('Error', 'Failed to load settings');
    } finally {
      setIsLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadSettings();
    setRefreshing(false);
  };

  const showSuccessAnimation = () => {
    setSaveSuccess(true);
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      Alert.alert('Error', 'Please enter an API key');
      return;
    }

    if (!validateElevenLabsKey(apiKey.trim())) {
      Alert.alert(
        'Invalid API Key',
        'ElevenLabs API keys should start with "sk_" and be at least 20 characters long.'
      );
      return;
    }

    try {
      setIsSaving(true);
      await saveApiKey(apiKey.trim());
      showSuccessAnimation();
      Alert.alert('Success', 'API key saved successfully');
    } catch (error) {
      console.error('Error saving API key:', error);
      Alert.alert('Error', 'Failed to save API key');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveApiKey = async () => {
    Alert.alert(
      'Remove API Key',
      'Are you sure you want to remove your API key?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              setIsSaving(true);
              await removeApiKey();
              setApiKey('');
              Alert.alert('Success', 'API key removed successfully');
            } catch (error) {
              console.error('Error removing API key:', error);
              Alert.alert('Error', 'Failed to remove API key');
            } finally {
              setIsSaving(false);
            }
          },
        },
      ]
    );
  };

  const handleSaveServerUrl = async () => {
    if (!serverUrl.trim()) {
      Alert.alert('Error', 'Please enter a server URL');
      return;
    }

    if (!serverUrl.startsWith('http://') && !serverUrl.startsWith('https://')) {
      Alert.alert('Invalid URL', 'Server URL must start with http:// or https://');
      return;
    }

    try {
      setIsSaving(true);
      await saveServerUrl(serverUrl.trim());
      showSuccessAnimation();
      Alert.alert(
        'Success',
        'Server URL saved successfully. Please restart the app for changes to take effect.'
      );
    } catch (error) {
      console.error('Error saving server URL:', error);
      Alert.alert('Error', 'Failed to save server URL');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetServerUrl = async () => {
    Alert.alert(
      'Reset Server URL',
      'Reset to default server URL based on your platform?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          onPress: async () => {
            try {
              setIsSaving(true);
              await saveServerUrl('');
              setServerUrl('');
              showSuccessAnimation();
              Alert.alert(
                'Success',
                'Server URL reset to default. Please restart the app for changes to take effect.'
              );
            } catch (error) {
              console.error('Error resetting server URL:', error);
              Alert.alert('Error', 'Failed to reset server URL');
            } finally {
              setIsSaving(false);
            }
          },
        },
      ]
    );
  };

  if (isLoading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerEmoji}>⚙️</Text>
          <Text style={styles.title}>Settings</Text>
          <Text style={styles.subtitle}>Configure your app</Text>
        </View>
        <View style={styles.loadingContainer}>
          <LoadingSpinner size={60} color={UI_CONFIG.COLORS.PRIMARY} />
          <Text style={styles.loadingText}>Loading settings...</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerEmoji}>⚙️</Text>
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.subtitle}>Configure your app</Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={UI_CONFIG.COLORS.PRIMARY}
            colors={[UI_CONFIG.COLORS.PRIMARY]}
          />
        }
      >
        <Animated.View style={{ opacity: fadeAnim }}>
          {/* Success Banner */}
          {saveSuccess && (
            <Animated.View
              style={[
                styles.successBanner,
                {
                  opacity: successAnim,
                  transform: [
                    {
                      translateY: successAnim.interpolate({
                        inputRange: [0, 1],
                        outputRange: [-20, 0],
                      }),
                    },
                  ],
                },
              ]}
            >
              <Text style={styles.successText}>✅ Settings saved successfully!</Text>
            </Animated.View>
          )}

          {/* API Key Section */}
          <AnimatedCard delay={0} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>🔑 ElevenLabs API Key</Text>
            <View style={styles.divider} />
            <Text style={styles.cardDescription}>
              Enter your ElevenLabs API key to use speech services. Get your key from{' '}
              <Text style={styles.link}>elevenlabs.io</Text>
            </Text>

            <View style={styles.inputContainer}>
              <TextInput
                style={styles.input}
                value={apiKey}
                onChangeText={setApiKey}
                placeholder="sk_..."
                placeholderTextColor={UI_CONFIG.COLORS.TEXT_SECONDARY}
                secureTextEntry={!showApiKey}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity
                style={styles.toggleButton}
                onPress={() => setShowApiKey(!showApiKey)}
                activeOpacity={0.7}
              >
                <Text style={styles.toggleButtonText}>{showApiKey ? '🙈' : '👁️'}</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.buttonRow}>
              <AnimatedButton
                title="Save API Key"
                onPress={handleSaveApiKey}
                variant="success"
                loading={isSaving}
                style={styles.flexButton}
              />
              {apiKey && (
                <AnimatedButton
                  title="Remove"
                  onPress={handleRemoveApiKey}
                  variant="danger"
                  disabled={isSaving}
                  style={styles.flexButton}
                />
              )}
            </View>
          </AnimatedCard>

          {/* Server URL Section */}
          <AnimatedCard delay={100} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>🌐 Server URL</Text>
            <View style={styles.divider} />
            <Text style={styles.cardDescription}>
              Custom server URL (optional). Leave empty to use default based on your platform.
            </Text>

            <TextInput
              style={styles.input}
              value={serverUrl}
              onChangeText={setServerUrl}
              placeholder={`Default: ${Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000'}`}
              placeholderTextColor={UI_CONFIG.COLORS.TEXT_SECONDARY}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />

            <View style={styles.buttonRow}>
              <AnimatedButton
                title="Save URL"
                onPress={handleSaveServerUrl}
                variant="success"
                loading={isSaving}
                style={styles.flexButton}
              />
              {serverUrl && (
                <AnimatedButton
                  title="Reset"
                  onPress={handleResetServerUrl}
                  variant="outline"
                  disabled={isSaving}
                  style={styles.flexButton}
                />
              )}
            </View>
          </AnimatedCard>

          {/* Info Section */}
          <AnimatedCard delay={200} elevation="sm" style={styles.infoCard}>
            <Text style={styles.infoTitle}>ℹ️ Information</Text>
            <View style={styles.divider} />
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>🔒</Text>
              <Text style={styles.infoText}>API keys are stored securely on your device</Text>
            </View>
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>🌐</Text>
              <Text style={styles.infoText}>Your API key is sent directly to ElevenLabs servers</Text>
            </View>
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>🔄</Text>
              <Text style={styles.infoText}>Server URL changes require app restart</Text>
            </View>
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>📱</Text>
              <Text style={styles.infoText}>For physical devices, use your computer's local IP address</Text>
            </View>
          </AnimatedCard>
        </Animated.View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: UI_CONFIG.COLORS.BACKGROUND,
  },
  header: {
    backgroundColor: UI_CONFIG.COLORS.PRIMARY,
    paddingTop: 50,
    paddingBottom: 20,
    paddingHorizontal: UI_CONFIG.SPACING.LG,
    alignItems: 'center',
    ...UI_CONFIG.SHADOWS.MD,
  },
  headerEmoji: {
    fontSize: 48,
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  title: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.HUGE,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_INVERSE,
    marginBottom: UI_CONFIG.SPACING.XXS,
  },
  subtitle: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_INVERSE,
    opacity: 0.9,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: UI_CONFIG.SPACING.XL,
  },
  loadingText: {
    marginTop: UI_CONFIG.SPACING.LG,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: UI_CONFIG.SPACING.LG,
  },
  successBanner: {
    backgroundColor: UI_CONFIG.COLORS.SUCCESS_LIGHT,
    padding: UI_CONFIG.SPACING.MD,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    marginBottom: UI_CONFIG.SPACING.LG,
    borderLeftWidth: 4,
    borderLeftColor: UI_CONFIG.COLORS.SUCCESS,
  },
  successText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
    color: UI_CONFIG.COLORS.SUCCESS,
    textAlign: 'center',
  },
  card: {
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  cardTitle: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  cardDescription: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginBottom: UI_CONFIG.SPACING.MD,
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.NORMAL,
  },
  divider: {
    height: 1,
    backgroundColor: UI_CONFIG.COLORS.BORDER_LIGHT,
    marginVertical: UI_CONFIG.SPACING.MD,
  },
  link: {
    color: UI_CONFIG.COLORS.PRIMARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: UI_CONFIG.SPACING.MD,
  },
  input: {
    flex: 1,
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    paddingHorizontal: UI_CONFIG.SPACING.MD,
    paddingVertical: UI_CONFIG.SPACING.MD,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  toggleButton: {
    marginLeft: UI_CONFIG.SPACING.SM,
    padding: UI_CONFIG.SPACING.SM,
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
  },
  toggleButtonText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: UI_CONFIG.SPACING.SM,
  },
  flexButton: {
    flex: 1,
  },
  infoCard: {
    marginBottom: UI_CONFIG.SPACING.XXL,
  },
  infoTitle: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  infoItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  infoIcon: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    marginRight: UI_CONFIG.SPACING.SM,
    marginTop: 2,
  },
  infoText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    flex: 1,
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.NORMAL,
  },
});

