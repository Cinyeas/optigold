import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class OptiGoldApp extends ConsumerWidget {
  OptiGoldApp({super.key});

  final _router = buildRouter();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // On iOS, wrap with CupertinoApp; on Android use MaterialApp.router
    if (Platform.isIOS) {
      return MaterialApp.router(
        title: 'OptiGold',
        theme: AppTheme.materialDark,
        routerConfig: _router,
        debugShowCheckedModeBanner: false,
        builder: (context, child) => CupertinoTheme(
          data: AppTheme.cupertinoTheme,
          child: child!,
        ),
      );
    }

    return MaterialApp.router(
      title: 'OptiGold',
      theme: AppTheme.materialDark,
      routerConfig: _router,
      debugShowCheckedModeBanner: false,
    );
  }
}
