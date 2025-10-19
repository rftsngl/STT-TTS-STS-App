import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
  Alert,
  RefreshControl,
} from 'react-native';
import { sttService, STTResponse } from '../api/services';
import { UI_CONFIG } from '../config/config';
import {
  AnimatedCard,
  AnimatedButton,
  LoadingSpinner,
  EmptyState,
  PulseAnimation,
} from '../components';

export const STTScreen: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<STTResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const recordingAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: UI_CONFIG.ANIMATIONS.DURATION.NORMAL,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    if (isRecording) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(recordingAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(recordingAnim, {
            toValue: 0,
            duration: 1000,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      recordingAnim.setValue(0);
    }
  }, [isRecording]);

  const handleTranscribe = async () => {
    if (!selectedFile) {
      Alert.alert('Error', 'Please select an audio file first');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const audioFile = {
        uri: selectedFile,
        type: 'audio/wav',
        name: 'recording.wav',
      };

      const data = await sttService.transcribe(audioFile, 'tr');
      setResult(data);
    } catch (err: any) {
      setError(err.message);
      Alert.alert('Error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFile = () => {
    setSelectedFile('file://path/to/recording.wav');
    Alert.alert('Success', 'Audio file selected');
  };

  const handleStartRecording = () => {
    setIsRecording(true);
    Alert.alert('Recording', 'Recording started (simulated)');
  };

  const handleStopRecording = () => {
    setIsRecording(false);
    setSelectedFile('file://path/to/new-recording.wav');
    Alert.alert('Success', 'Recording stopped and saved');
  };

  const handleClear = () => {
    setResult(null);
    setError(null);
    setSelectedFile(null);
  };

  const onRefresh = () => {
    setRefreshing(true);
    handleClear();
    setTimeout(() => setRefreshing(false), 500);
  };

  const recordingScale = recordingAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.1],
  });

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerEmoji}>🎤</Text>
          <Text style={styles.title}>Speech to Text</Text>
          <Text style={styles.subtitle}>Transcribe audio to text</Text>
        </View>
        <View style={styles.loadingContainer}>
          <LoadingSpinner size={60} color={UI_CONFIG.COLORS.PRIMARY} />
          <Text style={styles.loadingText}>Transcribing audio...</Text>
          <Text style={styles.loadingSubtext}>This may take a moment</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerEmoji}>🎤</Text>
        <Text style={styles.title}>Speech to Text</Text>
        <Text style={styles.subtitle}>Transcribe audio to text</Text>
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
          {/* Recording/File Selection Card */}
          <AnimatedCard delay={0} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>🎙️ Audio Input</Text>
            <View style={styles.divider} />

            {isRecording ? (
              <View style={styles.recordingContainer}>
                <PulseAnimation
                  size={100}
                  color={UI_CONFIG.COLORS.RECORDING}
                  pulseCount={3}
                />
                <Text style={styles.recordingText}>Recording...</Text>
                <AnimatedButton
                  title="Stop Recording"
                  onPress={handleStopRecording}
                  variant="danger"
                  style={styles.actionButton}
                />
              </View>
            ) : (
              <View>
                <AnimatedButton
                  title={selectedFile ? '✓ File Selected' : '📁 Choose File'}
                  onPress={handleSelectFile}
                  variant={selectedFile ? 'success' : 'outline'}
                  style={styles.actionButton}
                />
                {selectedFile && (
                  <Text style={styles.selectedFileText} numberOfLines={1}>
                    {selectedFile}
                  </Text>
                )}
                <View style={styles.orDivider}>
                  <View style={styles.orLine} />
                  <Text style={styles.orText}>OR</Text>
                  <View style={styles.orLine} />
                </View>
                <AnimatedButton
                  title="🎤 Start Recording"
                  onPress={handleStartRecording}
                  variant="primary"
                  style={styles.actionButton}
                />
              </View>
            )}
          </AnimatedCard>

          {/* Transcribe Button */}
          {selectedFile && !isRecording && (
            <AnimatedCard delay={100} elevation="sm" style={styles.card}>
              <AnimatedButton
                title="Transcribe Audio"
                onPress={handleTranscribe}
                variant="success"
                size="large"
                loading={loading}
                icon={<Text style={styles.buttonIcon}>🚀</Text>}
              />
              <AnimatedButton
                title="Clear"
                onPress={handleClear}
                variant="outline"
                size="small"
                style={styles.clearButton}
              />
            </AnimatedCard>
          )}

          {/* Error Display */}
          {error && (
            <AnimatedCard delay={200} elevation="md" style={styles.errorCard}>
              <EmptyState
                icon="❌"
                title="Transcription Failed"
                message={error}
                actionLabel="Try Again"
                onAction={handleClear}
              />
            </AnimatedCard>
          )}

          {/* Results */}
          {result && !error && (
            <>
              {/* Main Result Card */}
              <AnimatedCard delay={200} elevation="md" style={styles.card}>
                <Text style={styles.cardTitle}>📝 Transcription</Text>
                <View style={styles.divider} />
                <Text style={styles.resultText}>{result.text}</Text>
              </AnimatedCard>

              {/* Metadata Card */}
              <AnimatedCard delay={300} elevation="md" style={styles.card}>
                <Text style={styles.cardTitle}>ℹ️ Details</Text>
                <View style={styles.divider} />
                <View style={styles.metadataGrid}>
                  <View style={styles.metadataItem}>
                    <Text style={styles.metadataLabel}>Duration</Text>
                    <Text style={styles.metadataValue}>
                      {result.duration.toFixed(2)}s
                    </Text>
                  </View>
                  <View style={styles.metadataItem}>
                    <Text style={styles.metadataLabel}>Language</Text>
                    <Text style={styles.metadataValue}>{result.language}</Text>
                  </View>
                </View>
              </AnimatedCard>

              {/* Segments Card */}
              {result.segments && result.segments.length > 0 && (
                <AnimatedCard delay={400} elevation="md" style={styles.card}>
                  <Text style={styles.cardTitle}>📊 Segments</Text>
                  <View style={styles.divider} />
                  {result.segments.map((segment, index) => (
                    <View key={segment.id} style={styles.segmentItem}>
                      <Text style={styles.segmentTime}>
                        {segment.start.toFixed(2)}s - {segment.end.toFixed(2)}s
                      </Text>
                      <Text style={styles.segmentText}>{segment.text}</Text>
                    </View>
                  ))}
                </AnimatedCard>
              )}

              {/* Words Card */}
              {result.words && result.words.length > 0 && (
                <AnimatedCard delay={500} elevation="md" style={styles.card}>
                  <Text style={styles.cardTitle}>🔤 Words</Text>
                  <View style={styles.divider} />
                  <View style={styles.wordsContainer}>
                    {result.words.map((word, index) => (
                      <View key={index} style={styles.wordTag}>
                        <Text style={styles.wordText}>{word.word}</Text>
                        <Text style={styles.wordProb}>
                          {(word.probability * 100).toFixed(0)}%
                        </Text>
                      </View>
                    ))}
                  </View>
                </AnimatedCard>
              )}
            </>
          )}

          {/* Empty State */}
          {!result && !error && !selectedFile && !isRecording && (
            <AnimatedCard delay={100} elevation="sm">
              <EmptyState
                icon="🎤"
                title="No Audio Selected"
                message="Choose an audio file or start recording to begin transcription"
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
  recordingContainer: {
    alignItems: 'center',
    paddingVertical: UI_CONFIG.SPACING.XL,
  },
  recordingText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.RECORDING,
    marginTop: UI_CONFIG.SPACING.LG,
    marginBottom: UI_CONFIG.SPACING.XL,
  },
  actionButton: {
    marginTop: UI_CONFIG.SPACING.MD,
  },
  selectedFileText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginTop: UI_CONFIG.SPACING.SM,
    textAlign: 'center',
  },
  orDivider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: UI_CONFIG.SPACING.LG,
  },
  orLine: {
    flex: 1,
    height: 1,
    backgroundColor: UI_CONFIG.COLORS.BORDER_LIGHT,
  },
  orText: {
    marginHorizontal: UI_CONFIG.SPACING.MD,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
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
  resultText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.RELAXED,
  },
  metadataGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  metadataItem: {
    alignItems: 'center',
  },
  metadataLabel: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginBottom: UI_CONFIG.SPACING.XS,
  },
  metadataValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.PRIMARY,
  },
  segmentItem: {
    paddingVertical: UI_CONFIG.SPACING.SM,
    borderBottomWidth: 1,
    borderBottomColor: UI_CONFIG.COLORS.BORDER_LIGHT,
  },
  segmentTime: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginBottom: UI_CONFIG.SPACING.XXS,
  },
  segmentText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.NORMAL,
  },
  wordsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: UI_CONFIG.SPACING.SM,
  },
  wordTag: {
    backgroundColor: UI_CONFIG.COLORS.PRIMARY_LIGHT + '20',
    paddingHorizontal: UI_CONFIG.SPACING.SM,
    paddingVertical: UI_CONFIG.SPACING.XS,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
    flexDirection: 'row',
    alignItems: 'center',
    gap: UI_CONFIG.SPACING.XS,
  },
  wordText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.PRIMARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.MEDIUM,
  },
  wordProb: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XXS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
  },
});

