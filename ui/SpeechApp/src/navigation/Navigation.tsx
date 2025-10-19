import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { HomeScreen } from '../screens/HomeScreen';
import { STTScreen } from '../screens/STTScreen';
import { TTSScreen } from '../screens/TTSScreen';
import { VoicesScreen } from '../screens/VoicesScreen';
import { SettingsScreen } from '../screens/SettingsScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const HomeStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
    }}
  >
    <Stack.Screen name="HomeMain" component={HomeScreen} />
  </Stack.Navigator>
);

const STTStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
    }}
  >
    <Stack.Screen name="STTMain" component={STTScreen} />
  </Stack.Navigator>
);

const TTSStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
    }}
  >
    <Stack.Screen name="TTSMain" component={TTSScreen} />
  </Stack.Navigator>
);

const VoicesStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
    }}
  >
    <Stack.Screen name="VoicesMain" component={VoicesScreen} />
  </Stack.Navigator>
);

const SettingsStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
    }}
  >
    <Stack.Screen name="SettingsMain" component={SettingsScreen} />
  </Stack.Navigator>
);

export const Navigation = () => {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: '#007AFF',
          tabBarInactiveTintColor: '#999',
          tabBarStyle: {
            backgroundColor: '#FFFFFF',
            borderTopWidth: 1,
            borderTopColor: '#E0E0E0',
            paddingBottom: 5,
            paddingTop: 5,
          },
        }}
      >
        <Tab.Screen
          name="Home"
          component={HomeStack}
          options={{
            tabBarLabel: 'Home',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🏠</Text>,
          }}
        />
        <Tab.Screen
          name="STT"
          component={STTStack}
          options={{
            tabBarLabel: 'STT',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🎤</Text>,
          }}
        />
        <Tab.Screen
          name="TTS"
          component={TTSStack}
          options={{
            tabBarLabel: 'TTS',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🔊</Text>,
          }}
        />
        <Tab.Screen
          name="Voices"
          component={VoicesStack}
          options={{
            tabBarLabel: 'Voices',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🎵</Text>,
          }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsStack}
          options={{
            tabBarLabel: 'Settings',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>⚙️</Text>,
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

const Text = require('react-native').Text;

