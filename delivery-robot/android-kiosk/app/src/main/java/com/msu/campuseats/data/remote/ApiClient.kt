package com.msu.campuseats.data.remote

import com.msu.campuseats.BuildConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiClient {
    /**
     * Do not attach JWT to SimpleJWT endpoints (login/refresh) — avoids confusing server behavior on refresh.
     */
    private fun shouldAttachAuth(url: okhttp3.HttpUrl): Boolean {
        val path = url.encodedPath
        return !(path.startsWith("/api/auth/"))
    }

    private val authInterceptor = Interceptor { chain ->
        val original = chain.request()
        val token = synchronized(SessionStore.lock) { SessionStore.accessToken }
        val request = if (!shouldAttachAuth(original.url) || token.isNullOrBlank()) {
            original
        } else {
            original.newBuilder()
                .removeHeader("Authorization")
                .addHeader("Authorization", "Bearer $token")
                .build()
        }
        chain.proceed(request)
    }

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
    }

    private fun isAuthUrl(url: okhttp3.HttpUrl): Boolean {
        val path = url.encodedPath
        return path.startsWith("/api/auth/")
    }

    private val tokenRetryInterceptor = Interceptor { chain ->
        val req = chain.request()
        val res = chain.proceed(req)

        if (res.code != 401 || isAuthUrl(req.url)) {
            return@Interceptor res
        }

        // Single retry attempt after refreshing access token
        synchronized(SessionStore.lock) {
            SessionStore.refreshToken?.takeIf { it.isNotBlank() } ?: return@Interceptor res
        }

        val refreshed = refreshAccessTokenBlocking()
        res.close()

        if (!refreshed) {
            synchronized(SessionStore.lock) { SessionStore.clear() }
            return@Interceptor okhttp3.Response.Builder()
                .request(req)
                .protocol(okhttp3.Protocol.HTTP_1_1)
                .code(401)
                .message("Unauthorized")
                .body(okhttp3.ResponseBody.create(null, ByteArray(0)))
                .build()
        }

        val newAccess = synchronized(SessionStore.lock) { SessionStore.accessToken }
        val retryReq = req.newBuilder()
            .removeHeader("Authorization")
            .apply {
                if (!newAccess.isNullOrBlank()) {
                    addHeader("Authorization", "Bearer $newAccess")
                }
            }
            .build()

        return@Interceptor chain.proceed(retryReq)
    }

    private val client = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(tokenRetryInterceptor)
        .addInterceptor(logging)
        .build()

    val api: CampusEatsApi by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(CampusEatsApi::class.java)
    }
}

