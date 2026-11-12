package com.msu.campuseats.data.remote

object SessionStore {
    val lock = Any()

    @Volatile
    var accessToken: String? = null

    @Volatile
    var refreshToken: String? = null

    fun clear() {
        accessToken = null
        refreshToken = null
    }
}
