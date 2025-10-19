import React, { useRef } from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  Animated,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  GestureResponderEvent,
} from 'react-native';
import { UI_CONFIG } from '../config/config';

interface AnimatedButtonProps {
  title: string;
  onPress: (event: GestureResponderEvent) => void;
  variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'outline';
  size?: 'small' | 'medium' | 'large';
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const AnimatedButton: React.FC<AnimatedButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  size = 'medium',
  loading = false,
  disabled = false,
  icon,
  style,
  textStyle,
}) => {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    Animated.spring(scaleAnim, {
      toValue: 0.95,
      useNativeDriver: true,
      speed: 50,
      bounciness: 4,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      useNativeDriver: true,
      speed: 50,
      bounciness: 4,
    }).start();
  };

  const getButtonStyle = (): ViewStyle => {
    const baseStyle: ViewStyle = {
      ...styles.button,
      ...styles[`button_${size}`],
    };

    switch (variant) {
      case 'primary':
        return { ...baseStyle, backgroundColor: UI_CONFIG.COLORS.PRIMARY };
      case 'secondary':
        return { ...baseStyle, backgroundColor: UI_CONFIG.COLORS.ACCENT };
      case 'success':
        return { ...baseStyle, backgroundColor: UI_CONFIG.COLORS.SUCCESS };
      case 'danger':
        return { ...baseStyle, backgroundColor: UI_CONFIG.COLORS.ERROR };
      case 'outline':
        return {
          ...baseStyle,
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderColor: UI_CONFIG.COLORS.PRIMARY,
        };
      default:
        return baseStyle;
    }
  };

  const getTextStyle = (): TextStyle => {
    const baseStyle: TextStyle = {
      ...styles.text,
      ...styles[`text_${size}`],
    };

    if (variant === 'outline') {
      return { ...baseStyle, color: UI_CONFIG.COLORS.PRIMARY };
    }

    return baseStyle;
  };

  const isDisabled = disabled || loading;

  return (
    <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
      <TouchableOpacity
        style={[
          getButtonStyle(),
          isDisabled && styles.disabled,
          style,
        ]}
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={isDisabled}
        activeOpacity={0.8}
      >
        {loading ? (
          <ActivityIndicator
            color={variant === 'outline' ? UI_CONFIG.COLORS.PRIMARY : UI_CONFIG.COLORS.TEXT_INVERSE}
            size={size === 'small' ? 'small' : 'small'}
          />
        ) : (
          <>
            {icon && <>{icon}</>}
            <Text style={[getTextStyle(), textStyle]}>{title}</Text>
          </>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: UI_CONFIG.BORDER_RADIUS.MD,
    gap: UI_CONFIG.SPACING.SM,
    ...UI_CONFIG.SHADOWS.SM,
  },
  button_small: {
    paddingHorizontal: UI_CONFIG.SPACING.MD,
    paddingVertical: UI_CONFIG.SPACING.SM,
    minHeight: 36,
  },
  button_medium: {
    paddingHorizontal: UI_CONFIG.SPACING.LG,
    paddingVertical: UI_CONFIG.SPACING.MD,
    minHeight: UI_CONFIG.TOUCH_TARGET.MIN_SIZE,
  },
  button_large: {
    paddingHorizontal: UI_CONFIG.SPACING.XL,
    paddingVertical: UI_CONFIG.SPACING.LG,
    minHeight: 56,
  },
  text: {
    color: UI_CONFIG.COLORS.TEXT_INVERSE,
    fontWeight: UI_CONFIG.TYPOGRAPHY.FONT_WEIGHT.SEMIBOLD,
  },
  text_small: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.SM,
  },
  text_medium: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.LG,
  },
  text_large: {
    fontSize: UI_CONFIG.TYPOGRAPHY.FONT_SIZE.XL,
  },
  disabled: {
    opacity: 0.5,
  },
});

