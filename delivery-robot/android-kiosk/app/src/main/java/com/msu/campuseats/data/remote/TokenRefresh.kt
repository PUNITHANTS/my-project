package com.msu.campuseats.data.remote

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import com.msu.campuseats.BuildConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Synchronously refreshes the access token. Used from OkHttp interceptors only.
 *
 * Must not send Authorization header (backend refresh uses body only).
 */
fun refreshAccessTokenBlocking(): Boolean {
    val refresh = synchronized(SessionStore.lock) {
        SessionStore.refreshToken?.takeIf { it.isNotBlank() }
    } ?: return false

    val url = "${BuildConfig.API_BASE_URL.trimEnd('/')}/api/auth/token/refresh/"
    val bodyJson = Gson().toJson(mapOf("refresh" to refresh))
    val req = Request.Builder()
        .url(url)
        .post(bodyJson.toRequestBody(JSON_MEDIA))
        .build()

    return try {
        val resp = RefreshHttpClient.build().newCall(req).execute()
        if (!resp.isSuccessful) return false
        val respBody = resp.body?.string() ?: return false
        val refreshed = Gson().fromJson(respBody, TokenRefreshBody::class.java)
        synchronized(SessionStore.lock) {
            SessionStore.accessToken = refreshed.access
            // Rotate refresh token if backend returns one (typically it doesn't — keep existing)
            if (!refreshed.refresh.isNullOrBlank()) {
                SessionStore.refreshToken = refreshed.refresh
            }
        }
        true
    } catch (_: Exception) {
        false
    }
}

internal data class TokenRefreshBody(
    @SerializedName("access") val access: String,
    @SerializedName("refresh") val refresh: String? = null,
)

internal object RefreshHttpClient {
    fun build(): OkHttpClient = OkHttpClient.Builder().build()
}

internal val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
