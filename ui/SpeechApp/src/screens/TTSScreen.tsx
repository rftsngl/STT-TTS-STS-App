import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  TextInput,
  Animated,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { ttsService, voicesService, Voice } from '../api/services';
import { UI_CONFIG } from '../config/config';
import {
  AnimatedCard,
  AnimatedButton,
  LoadingSpinner,
  EmptyState,
} from '../components';

const MAX_CHARS = 5000;

export const TTSScreen: React.FC = () => {
  const [text, setText] = useState('');
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [loading, setLoading] = useState(false);
  const [voicesLoading, setVoicesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVoiceList, setShowVoiceList] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [synthesized, setSynthesized] = useState(false);

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const successAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadVoices();
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: UI_CONFIG.ANIMATIONS.DURATION.NORMAL,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    if (synthesized) {
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
      ]).start(() => setSynthesized(false));
    }
  }, [synthesized]);

  const loadVoices = async () => {
    try {
      setVoicesLoading(true);
      const data = await voicesService.getVoices();
      setVoices(data.voices);
      if (data.voices.length > 0) {
        setSelectedVoice(data.voices[0]);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setVoicesLoading(false);
    }
  };

  const handleSynthesize = async () => {
    if (!text.trim()) {
      Alert.alert('Error', 'Please enter text');
      return;
    }

    if (!selectedVoice) {
      Alert.alert('Error', 'Please select a voice');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const audioBlob = await ttsService.synthesize({
        text: text.trim(),
        voice_id: selectedVoice.voice_id,
        language: 'tr',
        output_format: 'mp3_22050_32',
      });

      setSynthesized(true);
      Alert.alert('Success', 'Audio generated successfully!');
    } catch (err: any) {
      setError(err.message);
      Alert.alert('Error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setText('');
    setError(null);
    setSynthesized(false);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadVoices();
    setRefreshing(false);
  };

  const charCount = text.length;
  const charPercentage = (charCount / MAX_CHARS) * 100;
  const charColor =
    charPercentage > 90
      ? UI_CONFIG.COLORS.ERROR
      : charPercentage > 70
      ? UI_CONFIG.COLORS.WARNING
      : UI_CONFIG.COLORS.SUCCESS;

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerEmoji}>🔊</Text>
          <Text style={styles.title}>Text to Speech</Text>
          <Text style={styles.subtitle}>Convert text to audio</Text>
        </View>
        <View style={styles.loadingContainer}>
          <LoadingSpinner size={60} color={UI_CONFIG.COLORS.PRIMARY} />
          <Text style={styles.loadingText}>Synthesizing audio...</Text>
          <Text style={styles.loadingSubtext}>Creating your audio file</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerEmoji}>🔊</Text>
        <Text style={styles.title}>Text to Speech</Text>
        <Text style={styles.subtitle}>Convert text to audio</Text>
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
          {synthesized && (
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
              <Text style={styles.successText}>✅ Audio synthesized successfully!</Text>
            </Animated.View>
          )}

          {/* Text Input Card */}
          <AnimatedCard delay={0} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>✍️ Enter Text</Text>
            <View style={styles.divider} />
            <TextInput
              style={styles.textInput}
              placeholder="Type or paste text to synthesize..."
              placeholderTextColor={UI_CONFIG.COLORS.TEXT_SECONDARY}
              value={text}
              onChangeText={(value) => {
                if (value.length <= MAX_CHARS) {
                  setText(value);
                }
              }}
              multiline
              numberOfLines={6}
              maxLength={MAX_CHARS}
            />
            <View style={styles.charCountContainer}>
              <Text style={[styles.charCount, { color: charColor }]}>
                {charCount} / {MAX_CHARS} characters
              </Text>
              <View style={styles.charProgressBar}>
                <View
                  style={[
                    styles.charProgress,
                    {
                      width: `${charPercentage}%`,
                      backgroundColor: charColor,
                    },
                  ]}
                />
              </View>
            </View>
          </AnimatedCard>

          {/* Voice Selection Card */}
          <AnimatedCard delay={100} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>🎙️ Select Voice</Text>
            <View style={styles.divider} />
            {voicesLoading ? (
              <View style={styles.voicesLoadingContainer}>
                <LoadingSpinner size={40} color={UI_CONFIG.COLORS.PRIMARY} />
                <Text style={styles.voicesLoadingText}>Loading voices...</Text>
              </View>
            ) : voices.length === 0 ? (
              <EmptyState
                icon="🎤"
                title="No Voices Available"
                message="No voices found. Please check your configuration."
              />
            ) : (
              <>
                <TouchableOpacity
                  style={styles.voiceSelector}
                  onPress={() => setShowVoiceList(!showVoiceList)}
                  activeOpacity={0.7}
                >
                  <View style={styles.voiceSelectorContent}>
                    <Text style={styles.voiceSelectorLabel}>Selected Voice</Text>
                    <Text style={styles.voiceSelectorValue}>
                      {selectedVoice ? selectedVoice.name : 'Select a voice'}
                    </Text>
                    {selectedVoice && (
                      <Text style={styles.voiceSelectorSource}>
                        Source: {selectedVoice.source}
                      </Text>
                    )}
                  </View>
                  <Text style={styles.voiceSelectorArrow}>
                    {showVoiceList ? '▲' : '▼'}
                  </Text>
                </TouchableOpacity>

                {showVoiceList && (
                  <View style={styles.voiceList}>
                    <ScrollView style={styles.voiceListScroll} nestedScrollEnabled>
                      {voices.map((voice, index) => (
                        <TouchableOpacity
                          key={voice.voice_id}
                          style={[
                            styles.voiceItem,
                            selectedVoice?.voice_id === voice.voice_id &&
                              styles.voiceItemSelected,
                            index === voices.length - 1 && styles.voiceItemLast,
                          ]}
                          onPress={() => {
                            setSelectedVoice(voice);
                            setShowVoiceList(false);
                          }}
                          activeOpacity={0.7}
                        >
                          <View style={styles.voiceItemContent}>
                            <Text
                              style={[
                                styles.voiceItemName,
                                selectedVoice?.voice_id === voice.voice_id &&
                                  styles.voiceItemNameSelected,
                              ]}
                            >
                              {voice.name}
                            </Text>
                            <Text style={styles.voiceItemSource}>{voice.source}</Text>
                          </View>
                          {selectedVoice?.voice_id === voice.voice_id && (
                            <Text style={styles.voiceItemCheck}>✓</Text>
                          )}
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                )}
              </>
            )}
          </AnimatedCard>

          {/* Action Buttons */}
          {text.trim() && selectedVoice && (
            <AnimatedCard delay={200} elevation="sm" style={styles.card}>
              <AnimatedButton
                title="Synthesize Audio"
                onPress={handleSynthesize}
                variant="success"
                size="large"
                loading={loading}
                icon={<Text style={styles.buttonIcon}>🚀</Text>}
              />
              <AnimatedButton
                title="Clear Text"
                onPress={handleClear}
                variant="outline"
                size="small"
                style={styles.clearButton}
              />
            </AnimatedCard>
          )}

          {/* Error Display */}
          {error && (
            <AnimatedCard delay={300} elevation="md" style={styles.errorCard}>
              <EmptyState
                icon="❌"
                title="Synthesis Failed"
                message={error}
                actionLabel="Try Again"
                onAction={() => setError(null)}
              />
            </AnimatedCard>
          )}

          {/* Info Card */}
          <AnimatedCard delay={400} elevation="sm" style={styles.infoCard}>
            <Text style={styles.infoTitle}>ℹ️ Information</Text>
            <View style={styles.divider} />
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>🌍</Text>
              <Text style={styles.infoText}>Supported languages: Turkish (tr)</Text>
            </View>
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>🎵</Text>
              <Text style={styles.infoText}>Output format: MP3 (22kHz, 32kbps)</Text>
            </View>
            <View style={styles.infoItem}>
              <Text style={styles.infoIcon}>📏</Text>
              <Text style={styles.infoText}>Maximum text length: 5000 characters</Text>
            </View>
          </AnimatedCard>

          {/* Empty State */}
          {!text.trim() && !error && (
            <AnimatedCard delay={100} elevation="sm">
              <EmptyState
                icon="✍️"
                title="No Text Entered"
                message="Enter some text above to synthesize it into speech"
              />
            </AnimatedCard>
          )}
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
  loadingSubtext: {
    marginTop: UI_CONFIG.SPACING.XS,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
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
  divider: {
    height: 1,
    backgroundColor: UI_CONFIG.COLORS.BORDER_LIGHT,
    marginVertical: UI_CONFIG.SPACING.MD,
  },
  textInput: {
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    padding: UI_CONFIG.SPACING.MD,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    textAlignVertical: 'top',
    minHeight: 120,
  },
  charCountContainer: {
    marginTop: UI_CONFIG.SPACING.SM,
  },
  charCount: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.MEDIUM,
    textAlign: 'right',
    marginBottom: UI_CONFIG.SPACING.XS,
  },
  charProgressBar: {
    height: 4,
    backgroundColor: UI_CONFIG.COLORS.BORDER_LIGHT,
    borderRadius: UI_CONFIG.BORDER_RADIUS.ROUND,
    overflow: 'hidden',
  },
  charProgress: {
    height: '100%',
    borderRadius: UI_CONFIG.BORDER_RADIUS.ROUND,
  },
  voicesLoadingContainer: {
    alignItems: 'center',
    paddingVertical: UI_CONFIG.SPACING.XL,
  },
  voicesLoadingText: {
    marginTop: UI_CONFIG.SPACING.MD,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
  },
  voiceSelector: {
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    padding: UI_CONFIG.SPACING.MD,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  voiceSelectorContent: {
    flex: 1,
  },
  voiceSelectorLabel: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginBottom: UI_CONFIG.SPACING.XXS,
  },
  voiceSelectorValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  voiceSelectorSource: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginTop: UI_CONFIG.SPACING.XXS,
  },
  voiceSelectorArrow: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginLeft: UI_CONFIG.SPACING.MD,
  },
  voiceList: {
    marginTop: UI_CONFIG.SPACING.MD,
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    maxHeight: 250,
    overflow: 'hidden',
  },
  voiceListScroll: {
    maxHeight: 250,
  },
  voiceItem: {
    padding: UI_CONFIG.SPACING.MD,
    borderBottomWidth: 1,
    borderBottomColor: UI_CONFIG.COLORS.BORDER_LIGHT,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  voiceItemLast: {
    borderBottomWidth: 0,
  },
  voiceItemSelected: {
    backgroundColor: UI_CONFIG.COLORS.PRIMARY_LIGHT + '20',
  },
  voiceItemContent: {
    flex: 1,
  },
  voiceItemName: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.MEDIUM,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  voiceItemNameSelected: {
    color: UI_CONFIG.COLORS.PRIMARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
  },
  voiceItemSource: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginTop: UI_CONFIG.SPACING.XXS,
  },
  voiceItemCheck: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    color: UI_CONFIG.COLORS.PRIMARY,
    marginLeft: UI_CONFIG.SPACING.SM,
  },
  clearButton: {
    marginTop: UI_CONFIG.SPACING.SM,
  },
  errorCard: {
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  buttonIcon: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
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
    alignItems: 'center',
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  infoIcon: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    marginRight: UI_CONFIG.SPACING.SM,
  },
  infoText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    flex: 1,
  },
});

