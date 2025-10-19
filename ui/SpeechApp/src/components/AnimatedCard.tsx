import React, { useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  ViewStyle,
  TouchableOpacity,
} from 'react-native';
import { UI_CONFIG } from '../config/config';

interface AnimatedCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
  delay?: number;
  elevation?: 'none' | 'sm' | 'md' | 'lg' | 'xl';
}

export const AnimatedCard: React.FC<AnimatedCardProps> = ({
  children,
  style,
  onPress,
  delay = 0,
  elevation = 'md',
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: UI_CONFIG.ANIMATIONS.DURATION.NORMAL,
        delay,
        useNativeDriver: true,
      }),
      Animated.spring(slideAnim, {
        toValue: 0,
        delay,
        useNativeDriver: true,
        tension: 50,
        friction: 7,
      }),
    ]).start();
  }, []);

  const handlePressIn = () => {
    if (onPress) {
      Animated.spring(scaleAnim, {
        toValue: 0.98,
        useNativeDriver: true,
        speed: 50,
      }).start();
    }
  };

  const handlePressOut = () => {
    if (onPress) {
      Animated.spring(scaleAnim, {
        toValue: 1,
        useNativeDriver: true,
        speed: 50,
      }).start();
    }
  };

  const getShadowStyle = () => {
    switch (elevation) {
      case 'none':
        return UI_CONFIG.SHADOWS.NONE;
      case 'sm':
        return UI_CONFIG.SHADOWS.SM;
      case 'md':
        return UI_CONFIG.SHADOWS.MD;
      case 'lg':
        return UI_CONFIG.SHADOWS.LG;
      case 'xl':
        return UI_CONFIG.SHADOWS.XL;
      default:
        return UI_CONFIG.SHADOWS.MD;
    }
  };

  const animatedStyle = {
    opacity: fadeAnim,
    transform: [
      { translateY: slideAnim },
      { scale: scaleAnim },
    ],
  };

  const cardContent = (
    <Animated.View
      style={[
        styles.card,
        getShadowStyle(),
        animatedStyle,
        style,
      ]}
    >
      {children}
    </Animated.View>
  );

  if (onPress) {
    return (
      <TouchableOpacity
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        activeOpacity={0.9}
      >
        {cardContent}
      </TouchableOpacity>
    );
  }

  return cardContent;
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: UI_CONFIG.COLORS.CARD_BACKGROUND,
    borderRadius: UI_CONFIG.BORDER_RADIUS.LG,
    padding: UI_CONFIG.SPACING.LG,
  },
});

