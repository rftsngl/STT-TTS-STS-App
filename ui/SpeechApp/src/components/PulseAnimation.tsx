import React, { useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  ViewStyle,
} from 'react-native';
import { UI_CONFIG } from '../config/config';

interface PulseAnimationProps {
  size?: number;
  color?: string;
  pulseCount?: number;
  style?: ViewStyle;
}

export const PulseAnimation: React.FC<PulseAnimationProps> = ({
  size = 100,
  color = UI_CONFIG.COLORS.RECORDING,
  pulseCount = 3,
  style,
}) => {
  const pulseAnims = useRef(
    Array.from({ length: pulseCount }, () => new Animated.Value(0))
  ).current;

  useEffect(() => {
    const animations = pulseAnims.map((anim, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(index * 400),
          Animated.parallel([
            Animated.timing(anim, {
              toValue: 1,
              duration: 1200,
              useNativeDriver: true,
            }),
          ]),
        ])
      )
    );

    animations.forEach((anim) => anim.start());

    return () => {
      animations.forEach((anim) => anim.stop());
    };
  }, []);

  return (
    <View style={[styles.container, { width: size * 2, height: size * 2 }, style]}>
      {pulseAnims.map((anim, index) => {
        const scale = anim.interpolate({
          inputRange: [0, 1],
          outputRange: [0.3, 2],
        });

        const opacity = anim.interpolate({
          inputRange: [0, 0.5, 1],
          outputRange: [0.6, 0.3, 0],
        });

        return (
          <Animated.View
            key={index}
            style={[
              styles.pulse,
              {
                width: size,
                height: size,
                borderRadius: size / 2,
                backgroundColor: color,
                opacity,
                transform: [{ scale }],
              },
            ]}
          />
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  pulse: {
    position: 'absolute',
  },
});

