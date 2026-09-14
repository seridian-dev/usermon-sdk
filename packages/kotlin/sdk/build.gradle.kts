plugins {
    id("com.android.library")
    kotlin("android")
    `maven-publish`
}

android {
    namespace = "dev.usermon.sdk"
    compileSdk = 34

    defaultConfig {
        minSdk = 21
        targetSdk = 34
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // No OkHttp dep: uses Android's HttpURLConnection to stay dep-free
}

publishing {
    publications {
        create<MavenPublication>("release") {
            groupId = "dev.usermon"
            artifactId = "usermon-sdk"
            version = "0.1.0"
            afterEvaluate {
                from(components["release"])
            }
        }
    }
}

// settings.gradle.kts (inlined comment — create separately if needed)
// rootProject.name = "usermon-sdk-android"
// include(":sdk")
