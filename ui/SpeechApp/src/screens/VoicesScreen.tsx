import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  FlatList,
  TextInput,
  Animated,
  RefreshControl,
} from 'react-native';
import { voicesService, Voice } from '../api/services';
import { UI_CONFIG } from '../config/config';
import {
  AnimatedCard,
  AnimatedButton,
  LoadingSpinner,
  EmptyState,
} from '../components';

export const VoicesScreen: React.FC = () => {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [filteredVoices, setFilteredVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const searchAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadVoices();
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: UI_CONFIG.ANIMATIONS.DURATION.NORMAL,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    filterVoices();
  }, [searchQuery, voices]);

  const loadVoices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await voicesService.getVoices();
      setVoices(data.voices);
    } catch (err: any) {
      setError(err.message);
      Alert.alert('Error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadVoices();
    setRefreshing(false);
  };

  const filterVoices = () => {
    if (!searchQuery.trim()) {
      setFilteredVoices(voices);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = voices.filter(
      (voice) =>
        voice.name.toLowerCase().includes(query) ||
        voice.source.toLowerCase().includes(query) ||
        voice.description?.toLowerCase().includes(query) ||
        Object.values(voice.labels || {}).some((label) =>
          label.toLowerCase().includes(query)
        )
    );
    setFilteredVoices(filtered);
  };

  const handleSearch = (text: string) => {
    setSearchQuery(text);
    Animated.spring(searchAnim, {
      toValue: text ? 1 : 0,
      useNativeDriver: true,
      tension: 50,
      friction: 7,
    }).start();
  };

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  const renderVoiceCard = ({ item, index }: { item: Voice; index: number }) => (
    <AnimatedCard
      delay={index * 50}
      elevation="md"
      style={styles.voiceCard}
      onPress={() => Alert.alert('Voice Selected', `You selected: ${item.name}`)}
    >
      <View style={styles.voiceHeader}>
        <Text style={styles.voiceName}>{item.name}</Text>
        <View style={styles.sourceBadge}>
          <Text style={styles.sourceBadgeText}>{item.source}</Text>
        </View>
      </View>

      {item.description && (
        <Text style={styles.voiceDescription}>{item.description}</Text>
      )}

      {item.labels && Object.keys(item.labels).length > 0 && (
        <View style={styles.labelsContainer}>
          {Object.entries(item.labels).map(([key, value]) => (
            <View key={key} style={styles.labelTag}>
              <Text style={styles.labelKey}>{key}:</Text>
              <Text style={styles.labelValue}> {value}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.voiceIdContainer}>
        <Text style={styles.voiceIdLabel}>Voice ID</Text>
        <Text style={styles.voiceId} numberOfLines={1}>
          {item.voice_id}
        </Text>
      </View>

      <AnimatedButton
        title="Use This Voice"
        onPress={() => Alert.alert('Voice Selected', `Using voice: ${item.name}`)}
        variant="primary"
        size="small"
      />
    </AnimatedCard>
  );

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerEmoji}>🎵</Text>
          <Text style={styles.title}>Available Voices</Text>
          <Text style={styles.subtitle}>Browse voice options</Text>
        </View>
        <View style={styles.loadingContainer}>
          <LoadingSpinner size={60} color={UI_CONFIG.COLORS.PRIMARY} />
          <Text style={styles.loadingText}>Loading voices...</Text>
          <Text style={styles.loadingSubtext}>Fetching available voices</Text>
        </View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerEmoji}>🎵</Text>
          <Text style={styles.title}>Available Voices</Text>
          <Text style={styles.subtitle}>Browse voice options</Text>
        </View>
        <View style={styles.errorContainer}>
          <EmptyState
            icon="❌"
            title="Failed to Load Voices"
            message={error}
            actionLabel="Retry"
            onAction={loadVoices}
          />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerEmoji}>🎵</Text>
        <Text style={styles.title}>Available Voices</Text>
        <Text style={styles.subtitle}>
          {voices.length} voice{voices.length !== 1 ? 's' : ''} available
        </Text>
      </View>

      <Animated.View style={[styles.searchContainer, { opacity: fadeAnim }]}>
        <View style={styles.searchInputContainer}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            style={styles.searchInput}
            placeholder="Search voices by name, source, or labels..."
            placeholderTextColor={UI_CONFIG.COLORS.TEXT_SECONDARY}
            value={searchQuery}
            onChangeText={handleSearch}
          />
          {searchQuery.length > 0 && (
            <AnimatedButton
              title="✕"
              onPress={handleClearSearch}
              variant="outline"
              size="small"
              style={styles.clearButton}
            />
          )}
        </View>
        {searchQuery.length > 0 && (
          <Text style={styles.searchResults}>
            {filteredVoices.length} result{filteredVoices.length !== 1 ? 's' : ''} found
          </Text>
        )}
      </Animated.View>

      <FlatList
        data={filteredVoices}
        renderItem={renderVoiceCard}
        keyExtractor={(item) => item.voice_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={UI_CONFIG.COLORS.PRIMARY}
            colors={[UI_CONFIG.COLORS.PRIMARY]}
          />
        }
        ListEmptyComponent={
          <EmptyState
            icon="🎤"
            title={searchQuery ? 'No Voices Found' : 'No Voices Available'}
            message={
              searchQuery
                ? `No voices match "${searchQuery}". Try a different search term.`
                : 'No voices are currently available. Pull down to refresh.'
            }
            actionLabel={searchQuery ? 'Clear Search' : undefined}
            onAction={searchQuery ? handleClearSearch : undefined}
          />
        }
      />
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: UI_CONFIG.SPACING.XL,
  },
  searchContainer: {
    backgroundColor: UI_CONFIG.COLORS.SURFACE,
    padding: UI_CONFIG.SPACING.LG,
    borderBottomWidth: 1,
    borderBottomColor: UI_CONFIG.COLORS.BORDER_LIGHT,
  },
  searchInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: UI_CONFIG.COLORS.BACKGROUND,
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER,
    paddingHorizontal: UI_CONFIG.SPACING.MD,
  },
  searchIcon: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    marginRight: UI_CONFIG.SPACING.SM,
  },
  searchInput: {
    flex: 1,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    paddingVertical: UI_CONFIG.SPACING.MD,
  },
  clearButton: {
    minWidth: 40,
    paddingHorizontal: UI_CONFIG.SPACING.SM,
  },
  searchResults: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginTop: UI_CONFIG.SPACING.SM,
    textAlign: 'center',
  },
  listContent: {
    padding: UI_CONFIG.SPACING.LG,
  },
  voiceCard: {
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  voiceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  voiceName: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    flex: 1,
    marginRight: UI_CONFIG.SPACING.SM,
  },
  sourceBadge: {
    backgroundColor: UI_CONFIG.COLORS.PRIMARY_LIGHT + '30',
    paddingHorizontal: UI_CONFIG.SPACING.SM,
    paddingVertical: UI_CONFIG.SPACING.XS,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
  },
  sourceBadgeText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.PRIMARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
  },
  voiceDescription: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginBottom: UI_CONFIG.SPACING.SM,
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.NORMAL,
  },
  labelsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: UI_CONFIG.SPACING.XS,
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  labelTag: {
    backgroundColor: UI_CONFIG.COLORS.BACKGROUND,
    paddingHorizontal: UI_CONFIG.SPACING.SM,
    paddingVertical: UI_CONFIG.SPACING.XS,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: UI_CONFIG.COLORS.BORDER_LIGHT,
  },
  labelKey: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
  },
  labelValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.MEDIUM,
  },
  voiceIdContainer: {
    backgroundColor: UI_CONFIG.COLORS.BACKGROUND,
    padding: UI_CONFIG.SPACING.SM,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
    marginBottom: UI_CONFIG.SPACING.MD,
  },
  voiceIdLabel: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XXS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
    marginBottom: UI_CONFIG.SPACING.XXS,
  },
  voiceId: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XS,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    fontFamily: 'monospace',
  },
});

