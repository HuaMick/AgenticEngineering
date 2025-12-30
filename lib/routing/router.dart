import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:myagents_frontend/features/pairing/pairing_screen.dart';
import 'package:myagents_frontend/features/remote_terminal/terminal_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      name: 'pairing',
      builder: (context, state) => const PairingScreen(),
    ),
    GoRoute(
      path: '/terminal',
      name: 'terminal',
      builder: (context, state) => const TerminalScreen(),
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    body: Center(
      child: Text('Page not found: ${state.uri}'),
    ),
  ),
);
