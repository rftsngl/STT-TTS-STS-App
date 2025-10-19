import React, { useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  ViewStyle,
} from 'react-native';
import { UI_CONFIG } from '../config/config';
import { AnimatedButton } from './AnimatedButton';

interface EmptyStateProps {
  icon: string;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  style?: ViewStyle;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  message,
  actionLabel,
  onAction,
  style,
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.8)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: UI_CONFIG.ANIMATIONS.DURATION.SLOW,
        useNativeDriver: true,
      }),
      Animated.spring(scaleAnim, {
        toValue: 1,
        tension: 50,
        friction: 7,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <Animated.View
      style={[
        styles.container,
        {
          opacity: fadeAnim,
          transform: [{ scale: scaleAnim }],
        },
        style,
      ]}
    >
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.message}>{message}</Text>
      {actionLabel && onAction && (
        <AnimatedButton
          title={actionLabel}
          onPress={onAction}
          variant="primary"
          size="medium"
          style={styles.button}
        />
      )}
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: UI_CONFIG.SPACING.XXL,
  },
  icon: {
    fontSize: 64,
    marginBottom: UI_CONFIG.SPACING.LG,
  },
  title: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XXL,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.BOLD,
    color: UI_CONFIG.COLORS.TEXT_PRIMARY,
    marginBottom: UI_CONFIG.SPACING.SM,
    textAlign: 'center',
  },
  message: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD,
    color: UI_CONFIG.COLORS.TEXT_SECONDARY,
    textAlign: 'center',
    lineHeight: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.MD * UI_CONFIG.TYPOGRAPHY.LINE_HEIGHT.RELAXED,
    marginBottom: UI_CONFIG.SPACING.XL,
  },
  button: {
    marginTop: UI_CONFIG.SPACING.MD,
  },
});

