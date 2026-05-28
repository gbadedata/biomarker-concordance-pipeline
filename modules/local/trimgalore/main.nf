process TRIMGALORE {
    tag "${meta.id}"
    label 'process_low'
    container 'quay.io/biocontainers/trim-galore:0.6.10--hdfd78af_0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*_trimmed.fq.gz'),   emit: reads
    tuple val(meta), path('*_trimming_report*'), emit: reports
    path 'versions.yml',                         emit: versions

    script:
    def prefix    = meta.id
    def paired    = meta.single_end ? '' : '--paired'
    def read_list = reads instanceof List ? reads.join(' ') : reads
    """
    trim_galore ${paired} --cores ${task.cpus} --gzip --basename ${prefix} ${read_list}

    for f in *_val_1.fq.gz; do [ -e "\$f" ] && mv "\$f" "${prefix}_R1_trimmed.fq.gz"; done
    for f in *_val_2.fq.gz; do [ -e "\$f" ] && mv "\$f" "${prefix}_R2_trimmed.fq.gz"; done

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        trim_galore: \$(trim_galore --version | grep version | sed 's/.*version //')
        cutadapt: \$(cutadapt --version)
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1_trimmed.fq.gz ${prefix}_R2_trimmed.fq.gz
    touch ${prefix}_R1_trimming_report.txt
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        trim_galore: 0.6.10
        cutadapt: 4.6
    VERSIONS
    """
}
