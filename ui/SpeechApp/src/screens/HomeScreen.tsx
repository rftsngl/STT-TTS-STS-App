import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Animated,
  Dimensions,
} from 'react-native';
import { healthService, HealthResponse } from '../api/services';
import { UI_CONFIG } from '../config/config';
import { AnimatedCard, AnimatedButton, LoadingSpinner, EmptyState } from '../components';

const { width } = Dimensions.get('window');

export const HomeScreen: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headerAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    checkHealth();
    animateHeader();
  }, []);

  const animateHeader = () => {
    Animated.parallel([
      Animated.timing(headerAnim, {
        toValue: 1,
        duration: UI_CONFIG.ANIMATIONS.DURATION.SLOW,
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: UI_CONFIG.ANIMATIONS.DURATION.SLOW,
        delay: 200,
        useNativeDriver: true,
      }),
    ]).start();
  };

  const checkHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await healthService.check();
      setHealth(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await checkHealth();
    setRefreshing(false);
  };

  const headerTranslateY = headerAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [-50, 0],
  });

  if (loading && !health) {
    return (
      <View style={styles.container}>
        <Animated.View
          style={[
            styles.header,
            {
              opacity: headerAnim,
              transform: [{ translateY: headerTranslateY }],
            },
          ]}
        >
          <Text style={styles.headerEmoji}>🎙️</Text>
          <Text style={styles.title}>TR Speech Stack</Text>
          <Text style={styles.subtitle}>Mobile Application</Text>
        </Animated.View>
        <View style={styles.loadingContainer}>
          <LoadingSpinner size={60} color={UI_CONFIG.COLORS.PRIMARY} />
          <Text style={styles.loadingText}>Loading health status...</Text>
        </View>
      </View>
    );
  }

  if (error && !health) {
    return (
      <View style={styles.container}>
        <Animated.View
          style={[
            styles.header,
            {
              opacity: headerAnim,
              transform: [{ translateY: headerTranslateY }],
            },
          ]}
        >
          <Text style={styles.headerEmoji}>🎙️</Text>
          <Text style={styles.title}>TR Speech Stack</Text>
          <Text style={styles.subtitle}>Mobile Application</Text>
        </Animated.View>
        <EmptyState
          icon="⚠️"
          title="Connection Error"
          message={error}
          actionLabel="Retry"
          onAction={checkHealth}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Animated.View
        style={[
          styles.header,
          {
            opacity: headerAnim,
            transform: [{ translateY: headerTranslateY }],
          },
        ]}
      >
        <Text style={styles.headerEmoji}>🎙️</Text>
        <Text style={styles.title}>TR Speech Stack</Text>
        <Text style={styles.subtitle}>Mobile Application</Text>
      </Animated.View>

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
          {/* Status Card */}
          <AnimatedCard delay={0} elevation="md" style={styles.statusCard}>
            <View style={styles.statusHeader}>
              <Text style={styles.statusTitle}>System Status</Text>
              <View
                style={[
                  styles.statusBadge,
                  health?.status === 'healthy'
                    ? styles.statusBadgeHealthy
                    : styles.statusBadgeUnhealthy,
                ]}
              >
                <Text style={styles.statusBadgeText}>
                  {health?.status === 'healthy' ? '✅ Healthy' : '❌ Unhealthy'}
                </Text>
              </View>
            </View>

            <View style={styles.divider} />

            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Device:</Text>
              <Text style={styles.infoValue}>{health?.device}</Text>
            </View>
          </AnimatedCard>

          {/* Features Card */}
          <AnimatedCard delay={100} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>🎯 Features</Text>
            <View style={styles.divider} />
            {health && Object.entries(health.features).map(([key, value]) => (
              <View key={key} style={styles.featureRow}>
                <Text style={styles.featureKey}>{key}</Text>
                <View
                  style={[
                    styles.featureValueContainer,
                    typeof value === 'boolean' && value
                      ? styles.featureEnabled
                      : styles.featureDisabled,
                  ]}
                >
                  <Text style={styles.featureValue}>
                    {typeof value === 'boolean'
                      ? value
                        ? '✓ Enabled'
                        : '✗ Disabled'
                      : value}
                  </Text>
                </View>
              </View>
            ))}
          </AnimatedCard>

          {/* Metrics Card */}
          <AnimatedCard delay={200} elevation="md" style={styles.card}>
            <Text style={styles.cardTitle}>📊 Performance Metrics</Text>
            <View style={styles.divider} />

            <View style={styles.metricCard}>
              <Text style={styles.metricValue}>{health?.metrics.count || 0}</Text>
              <Text style={styles.metricLabel}>Total Requests</Text>
            </View>

            <View style={styles.metricsGrid}>
              <View style={styles.metricCard}>
                <Text style={styles.metricValue}>
                  {health?.metrics.avg_total_ms.toFixed(0) || 0}
                  <Text style={styles.metricUnit}>ms</Text>
                </Text>
                <Text style={styles.metricLabel}>Avg Total Time</Text>
              </View>

              <View style={styles.metricCard}>
                <Text style={styles.metricValue}>
                  {health?.metrics.avg_stt_ms.toFixed(0) || 0}
                  <Text style={styles.metricUnit}>ms</Text>
                </Text>
                <Text style={styles.metricLabel}>Avg STT Time</Text>
              </View>
            </View>
          </AnimatedCard>

          {/* Quick Actions */}
          <AnimatedCard delay={300} elevation="sm" style={styles.actionsCard}>
            <Text style={styles.cardTitle}>⚡ Quick Actions</Text>
            <View style={styles.divider} />
            <View style={styles.actionsGrid}>
              <AnimatedButton
                title="Refresh"
                onPress={checkHealth}
                variant="outline"
                size="small"
                icon={<Text style={styles.buttonIcon}>🔄</Text>}
                style={styles.actionButton}
              />
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
  },
  loadingText: {
    marginTop: UI_CONFIG.SPACING.LG,
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: UI_CONFIG.SPACING.LG,
  },
  statusCard: {
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  statusHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: UI_CONFIG.SPACING.MD,
  },
  statusTitle: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  statusBadge: {
    paddingHorizontal: UI_CONFIG.SPACING.MD,
    paddingVertical: UI_CONFIG.SPACING.XS,
    borderRadius: UI_CONFIG.BORDER_RADIUS.ROUND,
  },
  statusBadgeHealthy: {
    backgroundColor: UI_CONFIG.COLORS.SUCCESS_LIGHT,
  },
  statusBadgeUnhealthy: {
    backgroundColor: UI_CONFIG.COLORS.ERROR_LIGHT,
  },
  statusBadgeText: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
  },
  divider: {
    height: 1,
    backgroundColor: UI_CONFIG.COLORS.BORDER_LIGHT,
    marginVertical: UI_CONFIG.SPACING.MD,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  infoLabel: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
  },
  infoValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
  },
  card: {
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  cardTitle: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    marginBottom: UI_CONFIG.SPACING.SM,
  },
  featureRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: UI_CONFIG.SPACING.SM,
  },
  featureKey: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    flex: 1,
  },
  featureValueContainer: {
    paddingHorizontal: UI_CONFIG.SPACING.MD,
    paddingVertical: UI_CONFIG.SPACING.XS,
    borderRadius: UI_CONFIG.BORDER_RADIUS.SM,
  },
  featureEnabled: {
    backgroundColor: UI_CONFIG.COLORS.SUCCESS_LIGHT,
  },
  featureDisabled: {
    backgroundColor: UI_CONFIG.COLORS.ERROR_LIGHT,
  },
  featureValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
  },
  metricCard: {
    alignItems: 'center',
    paddingVertical: UI_CONFIG.SPACING.MD,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: UI_CONFIG.SPACING.SM,
  },
  metricValue: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XXXL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.PRIMARY,
  },
  metricUnit: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.REGULAR,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
  },
  metricLabel: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    marginTop: UI_CONFIG.SPACING.XS,
  },
  actionsCard: {
    marginBottom: UI_CONFIG.SPACING.XXL,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: UI_CONFIG.SPACING.SM,
  },
  actionButton: {
    flex: 1,
    minWidth: (width - UI_CONFIG.SPACING.LG * 2 - UI_CONFIG.SPACING.SM) / 2,
  },
  buttonIcon: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
  },
});

