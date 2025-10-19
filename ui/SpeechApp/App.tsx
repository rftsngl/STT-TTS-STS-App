/**
 * TR Speech Stack Mobile Application
 * React Native Frontend for Speech Processing Services
 */

import React from 'react';
import { StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Navigation } from './src/navigation/Navigation';

function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="dark-content" backgroundColor="#007AFF" />
      <Navigation />
    </SafeAreaProvider>
  );
}

export default App;
