import 'package:flutter/material.dart';
import 'package:myagents_frontend/routing/router.dart';
import 'package:myagents_frontend/core/theme/app_theme.dart';

void main() {
  runApp(const MyAgentsApp());
}

class MyAgentsApp extends StatelessWidget {
  const MyAgentsApp({super.key});

  @override
  Widget build(BuildContext context) {
    // Note: Add MultiProvider wrapper when state management is needed
    // Feature worktrees will add providers here
    return MaterialApp.router(
      title: 'MyAgents Frontend',
      theme: AppTheme.lightTheme,
      routerConfig: appRouter,
    );
  }
}
