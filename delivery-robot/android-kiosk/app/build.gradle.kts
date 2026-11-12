import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val localProps = Properties()
val localPropsFile = rootProject.file("local.properties")
if (localPropsFile.exists()) {
    localPropsFile.reader(Charsets.UTF_8).use { localProps.load(it) }
}

fun localProp(key: String): String =
    System.getenv(envKey(key))?.trim()?.takeIf { it.isNotEmpty() }
        ?: localProps.getProperty(key)?.trim().orEmpty()

fun envKey(propKey: String): String =
    when (propKey) {
        "api.base.url" -> "KIOSK_API_BASE_URL"
        "kiosk.username" -> "KIOSK_USERNAME"
        "kiosk.password" -> "KIOSK_PASSWORD"
        else -> propKey.uppercase().replace('.', '_')
    }

fun escapedForJavaStringLiteral(value: String): String =
    buildString(value.length + 8) {
        for (ch in value) {
            when (ch) {
                '\\' -> append("\\\\")
                '"' -> append("\\\"")
                '\r' -> append("\\r")
                '\n' -> append("\\n")
                '\t' -> append("\\t")
                else -> append(ch)
            }
        }
    }

android {
    namespace = "com.msu.campuseats"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.msu.campuseats"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        val apiBaseUrl = localProp("api.base.url").also {
            check(it.isNotEmpty()) {
                "Set api.base.url in android-kiosk/local.properties (copy from local.properties.example) or set env KIOSK_API_BASE_URL"
            }
        }
        val kioskUser = localProp("kiosk.username").also {
            check(it.isNotEmpty()) {
                "Set kiosk.username in local.properties or set env KIOSK_USERNAME"
            }
        }
        val kioskPass = localProp("kiosk.password").also {
            check(it.isNotEmpty()) {
                "Set kiosk.password in local.properties or set env KIOSK_PASSWORD"
            }
        }

        buildConfigField("String", "API_BASE_URL", "\"" + escapedForJavaStringLiteral(apiBaseUrl) + "\"")
        buildConfigField("String", "KIOSK_USERNAME", "\"" + escapedForJavaStringLiteral(kioskUser) + "\"")
        buildConfigField("String", "KIOSK_PASSWORD", "\"" + escapedForJavaStringLiteral(kioskPass) + "\"")
    }

    buildTypes {
        debug {
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")

    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
}
