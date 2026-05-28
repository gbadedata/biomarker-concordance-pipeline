process GATK_MARKDUPLICATES {
    tag "${meta.id}"
    label 'process_medium'
    container 'broadinstitute/gatk:4.5.0.0'

    input:
    tuple val(meta), path(bam), path(bai)

    output:
    tuple val(meta), path('*.markdup.bam'),     emit: bam
    tuple val(meta), path('*.markdup.bam.bai'), emit: bai
    tuple val(meta), path('*.metrics.txt'),     emit: metrics
    path 'versions.yml',                        emit: versions

    script:
    def prefix    = meta.id
    def avail_mem = (task.memory.giga * 0.8).intValue()
    """
    gatk --java-options "-Xmx${avail_mem}g" MarkDuplicates \\
        --INPUT ${bam} \\
        --OUTPUT ${prefix}.markdup.bam \\
        --METRICS_FILE ${prefix}.markdup.metrics.txt \\
        --OPTICAL_DUPLICATE_PIXEL_DISTANCE 2500 \\
        --CREATE_INDEX true \\
        --VALIDATION_STRINGENCY SILENT \\
        --ASSUME_SORT_ORDER coordinate

    if [ -f "${prefix}.markdup.bai" ]; then
        mv ${prefix}.markdup.bai ${prefix}.markdup.bam.bai
    fi

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: \$(gatk --version 2>&1 | grep -o '[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+' | head -1)
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.markdup.bam ${prefix}.markdup.bam.bai ${prefix}.markdup.metrics.txt
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: 4.5.0.0
    VERSIONS
    """
}
